from django.contrib import admin, messages

import secrets
import string
from decimal import Decimal

from greenmarv.commission_calculations import _calculate_paid_commission, _calculate_pending_commission
from payment.sms_helpers import _format_sa_phone
from payment.utils import send_sms_smsportal
from .models import Category, Customer, InfluencerClick, Product, Profile, Influencer, DiscountCode
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone

from django.db.models import Sum, Count
from payment.models import Order

from django.utils.html import format_html
from django.utils.safestring import mark_safe


# Register your models here.

admin.site.register(Category)
admin.site.register(Customer)
admin.site.register(Product)
#admin.site.register(Order)
admin.site.register(Profile)
#admin.site.register(Influencer)
admin.site.register(DiscountCode)




# ================================================================
# 1. INFLUENCER ADMIN — "Create dashboard account" bulk action
# ================================================================
 
def _generate_password(length=12):
    """Generate a secure random password that's still readable."""
    # Avoid ambiguous chars: 0/O, 1/l/I
    alphabet = string.ascii_letters.replace('l', '').replace('I', '').replace('O', '') + \
               string.digits.replace('0', '').replace('1', '') + \
               '!@#$%^&*'
    return ''.join(secrets.choice(alphabet) for _ in range(length))
 

 
@admin.action(description="🔑 Create dashboard account + SMS credentials")
def create_dashboard_account(modeladmin, request, queryset):
    """
    For each selected influencer without a User account:
      1. Create a Django User with username=slug + random password
      2. Link the User to the Influencer
      3. SMS the influencer with login URL + credentials
      4. Show the password in admin message (fallback if SMS fails)
    """
    site_url = getattr(settings, 'SITE_URL', 'https://greenmarvel.co.za').rstrip('/')
    login_url = f"{site_url}/influencer/login/"
 
    created = 0
    already_had = 0
    sms_sent = 0
    sms_failed = 0
 
    for influencer in queryset:
        if influencer.user:
            already_had += 1
            messages.info(
                request,
                f"ℹ️ {influencer.name} already has account '{influencer.user.username}'"
            )
            continue
 
        if not influencer.slug:
            messages.error(
                request,
                f"❌ {influencer.name} has no slug — save them first to generate one."
            )
            continue
 
        # Check if slug collides with an existing username
        if User.objects.filter(username=influencer.slug).exists():
            messages.error(
                request,
                f"❌ Username '{influencer.slug}' is already taken. "
                f"Edit {influencer.name}'s slug to something unique."
            )
            continue
 
        # Generate password + create user
        password = _generate_password()
        user = User.objects.create_user(
            username=influencer.slug,
            password=password,
            email=influencer.email or '',
            first_name=influencer.name.split()[0] if influencer.name else '',
            last_name=' '.join(influencer.name.split()[1:]) if ' ' in (influencer.name or '') else '',
        )
 
        influencer.user = user
        influencer.save()
        created += 1
 
        # Always show the credentials in admin — critical fallback if SMS fails
        messages.success(
            request,
            f"✅ Account created for {influencer.name} — "
            f"username: '{influencer.slug}', password: '{password}' — "
            f"COPY THIS NOW, it won't be shown again."
        )
 
        # Try SMS
        sent = _sms_credentials(influencer, password, login_url)
        if sent:
            sms_sent += 1
        else:
            sms_failed += 1
 
    # Summary
    if created:
        messages.success(
            request,
            f"🔑 Created {created} dashboard account{'s' if created > 1 else ''} · "
            f"{sms_sent} SMS sent · {sms_failed} SMS failed"
        )
    if already_had and created == 0:
        messages.info(
            request,
            f"All selected influencers already had accounts — nothing to create."
        )
 
 
def _sms_credentials(influencer, password, login_url):
    """SMS the influencer their login credentials. Returns True if sent."""
    if not influencer.phone:
        return False
 
    phone = _format_sa_phone(influencer.phone)
    if not phone:
        return False
 
    message = (
        f"🌿 Welcome to Marvelously Green, {influencer.name.split()[0]}! "
        f"Your dashboard: {login_url} "
        f"Username: {influencer.slug} | "
        f"Password: {password} "
        f"Please change your password after signing in."
    )
 
    try:
        result = send_sms_smsportal(phone, message)
        return result.get('success', False)
    except Exception:
        return False





@admin.register(Influencer)
class InfluencerAdmin(admin.ModelAdmin):
    list_display = [
        'name', 
        'slug', 
        'commission_rate', 
        'is_active', 
        'has_dashboard_access', 
        'total_orders', 
        'pending_commission_display', 
        'date_joined',
    ]
    list_filter = ['is_active', 'date_joined']
    search_fields = ['name', 'email', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    
    # FIX: Ensure all custom model admin methods displayed are marked readonly
    readonly_fields = [
        'date_joined', 
        'referral_url_display', 
        'payout_summary',
        'pending_commission_display',
    ]

    actions = [create_dashboard_account]

    fieldsets = (
        ('Identity', {
            'fields': ('name', 'slug', 'bio', 'profile_image'),
        }),
        ('Contact', {
            'fields': ('phone', 'email'),
        }),
        ('Programme', {
            'fields': ('commission_rate', 'is_active', 'referral_url_display'),
        }),
        ('Dashboard access', {
            'fields': ('user',),
            'description': "Link a Django User to grant dashboard access, OR "
                           "use the 'Create dashboard account' action to automate it.",
        }),
        ('Payout summary', {
            'fields': ('payout_summary',),
        }),
        ('Meta', {
            'fields': ('date_joined',),
            'classes': ('collapse',),
        }),
    )

    # FIX: Optimization to prevent N+1 queries for the orders count
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(_total_orders=Count('orders'))

    def has_dashboard_access(self, obj):
        return obj.user is not None
    has_dashboard_access.boolean = True
    has_dashboard_access.short_description = 'Dashboard'

    # FIX: Uses the annotated value from get_queryset
    def total_orders(self, obj):
        return obj._total_orders
    total_orders.short_description = 'Orders'
    total_orders.admin_order_field = '_total_orders'  # Makes column sortable!

    # FIX: Secure variable passing into format_html
    def pending_commission_display(self, obj):
        """Show pending commission as a styled badge in list view."""
        pending = _calculate_pending_commission(obj)
        if pending > 0:
            return format_html(
                '<span style="color: #c5a059; font-weight: 700;">R{}</span>', 
                f"{pending:.2f}"
            )
        return mark_safe('<span style="color: #999;">—</span>')
    pending_commission_display.short_description = 'Owed'

    # FIX: Turning the referral URL into an actual clickable link
    def referral_url_display(self, obj):
        if not obj.slug:
            return "— save first to generate URL —"
        base = getattr(settings, 'SITE_URL', 'https://greenmarvel.co.za').rstrip('/')
        url = f"{base}{obj.referral_url_path}"
        return format_html('<a href="{0}" target="_blank">{0}</a>', url)
    referral_url_display.short_description = 'Referral URL'

    # FIX: Secure variable interpolation for the breakdown layout
    def payout_summary(self, obj):
        """Full payout summary in detail view."""
        paid = _calculate_paid_commission(obj)
        pending = _calculate_pending_commission(obj)
        total = paid + pending
        return format_html(
            '<div style="line-height: 1.6;">'
            '<strong>Total earned (all time):</strong> R{}<br>'
            '<strong>Paid out:</strong> R{}<br>'
            '<strong style="color: #c5a059;">Pending payout:</strong> R{}'
            '</div>', 
            f"{total:.2f}", 
            f"{paid:.2f}", 
            f"{pending:.2f}"
        )
    payout_summary.short_description = 'Payout summary'


"""
@admin.register(Influencer)
class InfluencerAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'slug',
        'commission_rate',
        'is_active',
        'has_dashboard_access',
        'total_orders',
        'pending_commission_display',   # NEW in Phase 5
        'date_joined',
    ]
    list_filter = ['is_active', 'date_joined']
    search_fields = ['name', 'email', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = [
        'date_joined',
        'referral_url_display',
        'payout_summary',             # NEW in Phase 5
    ]
 
    # Register the Phase 5 action
    actions = [create_dashboard_account]
 
    fieldsets = (
        ('Identity', {
            'fields': ('name', 'slug', 'bio', 'profile_image'),
        }),
        ('Contact', {
            'fields': ('phone', 'email'),
        }),
        ('Programme', {
            'fields': ('commission_rate', 'is_active', 'referral_url_display'),
        }),
        ('Dashboard access', {
            'fields': ('user',),
            'description': "Link a Django User to grant dashboard access, OR "
                           "use the 'Create dashboard account' action to automate it.",
        }),
        ('Payout summary', {
            'fields': ('payout_summary',),
        }),
        ('Meta', {
            'fields': ('date_joined',),
            'classes': ('collapse',),
        }),
    )
 
    def has_dashboard_access(self, obj):
        return obj.user is not None
    has_dashboard_access.boolean = True
    has_dashboard_access.short_description = 'Dashboard'
 
    def total_orders(self, obj):
        return obj.orders.count()
    total_orders.short_description = 'Orders'
 
    def pending_commission_display(self, obj):
        #Show pending commission as a styled badge in list view.
        pending = _calculate_pending_commission(obj)
        if pending > 0:
            return format_html(
                '<span style="color: #c5a059; font-weight: 700;">R{}</span>',
                f"{pending:.2f}"
            )
        return format_html('<span style="color: #999;">—</span>')
    pending_commission_display.short_description = 'Owed'
 
    def referral_url_display(self, obj):
        if not obj.slug:
            return "— save first to generate URL —"
        
        base = getattr(settings, 'SITE_URL', 'https://greenmarvel.co.za').rstrip('/')
        return f"{base}{obj.referral_url_path}"
    referral_url_display.short_description = 'Referral URL'
 
    def payout_summary(self, obj):
        #Full payout summary in detail view.
        paid = _calculate_paid_commission(obj)
        pending = _calculate_pending_commission(obj)
        total = paid + pending
 
        return format_html(
            '<div style="line-height: 1.6;">'
            '<strong>Total earned (all time):</strong> R{}<br>'
            '<strong>Paid out:</strong> R{}<br>'
            '<strong style="color: #c5a059;">Pending payout:</strong> R{}'
            '</div>',
            f"{total:.2f}", f"{paid:.2f}", f"{pending:.2f}"
        )
    payout_summary.short_description = 'Payout summary'
"""



"""
@admin.register(Influencer)
class InfluencerAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'slug',
        'commission_rate',
        'is_active',
        'has_dashboard_access',
        'total_orders',
        'date_joined',
    ]
    list_filter = ['is_active', 'date_joined']
    search_fields = ['name', 'email', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['date_joined', 'referral_url_display']
 
    fieldsets = (
        ('Identity', {
            'fields': ('name', 'slug', 'bio', 'profile_image'),
        }),
        ('Contact', {
            'fields': ('phone', 'email'),
        }),
        ('Programme', {
            'fields': ('commission_rate', 'is_active', 'referral_url_display'),
        }),
        ('Dashboard access', {
            'fields': ('user',),
            'description': "Link a Django User to grant this influencer access to their dashboard. "
                           "User can be created manually or via the 'Create dashboard account' "
                           "action (Phase 5).",
        }),
        ('Meta', {
            'fields': ('date_joined',),
            'classes': ('collapse',),
        }),
    )
 
    def has_dashboard_access(self, obj):
        return obj.user is not None
    has_dashboard_access.boolean = True
    has_dashboard_access.short_description = 'Dashboard'
 
    def total_orders(self, obj):
        return obj.orders.count()
    total_orders.short_description = 'Orders'
 
    def referral_url_display(self, obj):
        if not obj.slug:
            return "— save first to generate URL —"
        
        base = getattr(settings, 'SITE_URL', 'https://greenmarvel.co.za').rstrip('/')
        return f"{base}{obj.referral_url_path}"
    referral_url_display.short_description = 'Referral URL'
"""
 
@admin.register(InfluencerClick)
class InfluencerClickAdmin(admin.ModelAdmin):
    list_display = ['influencer', 'clicked_at', 'product_slug', 'referrer_domain']
    list_filter = ['influencer', 'clicked_at']
    search_fields = ['influencer__name', 'product_slug']
    date_hierarchy = 'clicked_at'
    readonly_fields = [
        'influencer', 'clicked_at', 'product_slug',
        'user_agent', 'ip_hash', 'session_key', 'referrer_domain',
    ]
 
    def has_add_permission(self, request):
        # Clicks are only created automatically by the landing view
        return False



# Mix profile info and user info
class ProfileInline(admin.StackedInline):
	model = Profile

# Extend User Model
class UserAdmin(admin.ModelAdmin):
	model = User
	field = ["username", "first_name", "last_name", "email"]
	inlines = [ProfileInline]

# Unregister the old way
admin.site.unregister(User)

# Re-Register the new way
admin.site.register(User, UserAdmin)

