from django.contrib import admin
from .models import ShippingAddress, Order, OrderItem, PayfastPayment, CourierGuy
from django.contrib.auth.models import User
from django.utils import timezone

from django.utils.safestring import mark_safe
from django.utils.html import format_html
#from .models import Order, OrderItem

admin.site.register(ShippingAddress)
admin.site.register(PayfastPayment)
admin.site.register(CourierGuy)

"""
# Register your models here.
admin.site.register(ShippingAddress)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(PayfastPayment)
admin.site.register(CourierGuy)

# Create an OrderItem Inline
class OrderItemInline(admin.StackedInline):
	model = OrderItem
	extra = 0

# Extend our Order Model
class OrderAdmin(admin.ModelAdmin):
	model = Order
	readonly_fields = ["date_ordered"]
	fields = ["user", "full_name", "email", "shipping_address", "amount_paid", "date_ordered", "shipped", "date_shipped"]
	inlines = [OrderItemInline]

# Unregister Order Model
admin.site.unregister(Order)

# Re-Register our Order AND OrderAdmin
admin.site.register(Order, OrderAdmin)
"""



#Updated Django admin for Order, with shipping service columns and margin tracking.

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'price')
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """
    Admin view for orders, showing shipping selection and margin per order.
    """
    
    list_display = (
        'id',
        'full_name',
        'status_badge',
        'amount_paid_display',
        'shipping_service_badge',  # ← NEW
        'shipping_margin_display',  # ← NEW
        'courier_booked',           # ← NEW (you fill this in after booking)
        'tracking_number',          # ← NEW
        'date_ordered',
    )
    
    list_filter = (
        'status',
        'shipping_service_code',  # ← NEW: filter by tier (Economy/Standard/Express)
        'date_ordered',
        'shipped',
    )
    
    search_fields = (
        'id',
        'full_name',
        'email',
        'phone',
        'tracking_number',
    )
    
    readonly_fields = (
        'date_ordered',
        'date_paid',
        'shipping_margin_display',
        'amount_paid',
    )
    
    fieldsets = (
        ('Customer', {
            'fields': ('user', 'full_name', 'email', 'phone', 'shipping_address'),
        }),
        ('Order Details', {
            'fields': ('amount_paid', 'status', 'date_ordered', 'date_paid'),
        }),
        ('Shipping', {
            'fields': (
                'shipping_service_code',
                'shipping_service_name',
                'shipping_cost',
                'shipping_actual_cost',
                'shipping_margin_display',
                'courier_booked',
                'tracking_number',
                'shipped',
                'date_shipped',
            ),
            'description': 'Customer chose the service tier — you book the actual courier via Bob Go and fill in the courier name and tracking number here.',
        }),
    )
    
    inlines = [OrderItemInline]
    
    # ============================================
    # CUSTOM COLUMN RENDERS
    # ============================================
    
    def status_badge(self, obj):
        """Color-coded status badge for quick scanning."""
        colors = {
            'pending_payment': '#999',
            'paid':            '#2d5016',
            'cancelled':       '#c0392b',
            'failed':          '#c0392b',
        }
        color = colors.get(obj.status, '#666')
        label = obj.get_status_display() if hasattr(obj, 'get_status_display') else obj.status
        return format_html(
            '<span style="background:{}; color:white; padding:2px 8px; border-radius:10px; font-size:0.75rem; font-weight:700;">{}</span>',
            color, label.upper()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def amount_paid_display(self, obj):
        return format_html('<strong>R{}</strong>', f"{obj.amount_paid:.2f}")
    amount_paid_display.short_description = 'Total'
    amount_paid_display.admin_order_field = 'amount_paid'
    
    def shipping_service_badge(self, obj):
        """Color-coded shipping tier badge."""
        if not obj.shipping_service_code:
            return mark_safe('<span style="color:#999;">—</span>')
        
        colors = {
            'economy':  ('#c5a059', 'ECONOMY'),
            'standard': ('#4CAF50', 'STANDARD'),
            'express':  ('#2d5016', 'EXPRESS'),
        }
        color, label = colors.get(obj.shipping_service_code, ('#999', obj.shipping_service_code.upper()))
        cost = f"R{obj.shipping_cost:.0f}" if obj.shipping_cost else ''
        return format_html(
            '<span style="background:{}; color:white; padding:2px 7px; border-radius:8px; font-size:0.7rem; font-weight:700; letter-spacing:1px;">{}</span> <small>{}</small>',
            color, label, cost
        )
    shipping_service_badge.short_description = 'Shipping'
    shipping_service_badge.admin_order_field = 'shipping_service_code'
    
    def shipping_margin_display(self, obj):
        """Show the margin made on shipping for this order."""
        margin = obj.shipping_margin
        if margin > 0:
            return format_html(
                '<span style="color:#2d5016; font-weight:700;">+R{}</span>',
                f"{margin:.2f}"
            )
        elif margin < 0:
            return format_html(
                '<span style="color:#c0392b; font-weight:700;">−R{}</span>',
                f"{abs(margin):.2f}"
            )
        else:
            return mark_safe('<span style="color:#999;">R0.00</span>')
    shipping_margin_display.short_description = 'Ship. Margin'
    
    # ============================================
    # BULK ACTIONS
    # ============================================
    
    actions = ['mark_as_shipped']
    
    def mark_as_shipped(self, request, queryset):
        """Bulk action to mark selected orders as shipped."""
        count = queryset.update(shipped=True, date_shipped=timezone.now())
        self.message_user(request, f"{count} order(s) marked as shipped.")
    mark_as_shipped.short_description = "Mark selected orders as shipped"