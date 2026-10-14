from django.contrib import admin
from .models import Category, Customer, InfluencerClick, Product, Profile, Influencer, DiscountCode
from django.contrib.auth.models import User
from django.conf import settings


# Register your models here.

admin.site.register(Category)
admin.site.register(Customer)
admin.site.register(Product)
#admin.site.register(Order)
admin.site.register(Profile)
#admin.site.register(Influencer)
admin.site.register(DiscountCode)



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

