from django.contrib import admin,messages

from payment.sms_helpers import _format_sa_phone
from payment.utils import send_sms_smsportal
from .models import ShippingAddress, Order, OrderItem, PayfastPayment, CourierGuy
from django.contrib.auth.models import User
from django.utils import timezone

from django.utils.safestring import mark_safe
from django.utils.html import format_html

from decimal import Decimal




admin.site.register(ShippingAddress)
admin.site.register(PayfastPayment)
admin.site.register(CourierGuy)




# ================================================================
# 2. ORDER ADMIN — "Mark commission as paid" bulk action
# ================================================================
 
@admin.action(description="💰 Mark commission as paid out to influencer")
def mark_commission_paid(modeladmin, request, queryset):
    """
    Bulk-mark attributed orders as having had their commission paid out.
    Only operates on orders that:
      - Have an influencer attributed
      - Are already paid (status='paid' or beyond)
      - Haven't already had commission paid out
    
    Also sends an SMS to each influencer with their payout total.
    """
    PAID_STATUSES = ('paid', 'dispatched', 'in_transit', 'delivered', 'collected')
 
    # Filter down to eligible orders
    eligible = queryset.filter(
        influencer__isnull=False,
        status__in=PAID_STATUSES,
        commission_paid_out_at__isnull=True,
    )
 
    if not eligible.exists():
        messages.warning(
            request,
            "No eligible orders selected. Orders must be: attributed to an "
            "influencer, paid, and not already paid out."
        )
        return
 
    # Group by influencer so we can SMS each one their total payout
    now = timezone.now()
    payout_by_influencer = {}  # influencer_id → list of (order, commission)
 
    for order in eligible.select_related('influencer').prefetch_related('orderitem_set'):
        subtotal = sum(
            item.price * item.quantity
            for item in order.orderitem_set.all()
        )
        commission = (
            subtotal * Decimal(str(order.influencer.commission_rate)) / Decimal('100')
        ).quantize(Decimal('0.01'))
 
        payout_by_influencer.setdefault(order.influencer, []).append((order, commission))
 
    # Mark paid + SMS each influencer
    marked = 0
    sms_sent = 0
 
    for influencer, order_commissions in payout_by_influencer.items():
        order_ids = [oc[0].id for oc in order_commissions]
        total_commission = sum(oc[1] for oc in order_commissions)
 
        # Bulk update timestamps
        Order.objects.filter(id__in=order_ids).update(commission_paid_out_at=now)
        marked += len(order_ids)
 
        # SMS the influencer
        if _sms_payout_notification(influencer, total_commission, len(order_ids)):
            sms_sent += 1
 
    messages.success(
        request,
        f"💰 Marked {marked} order{'s' if marked > 1 else ''} as paid out · "
        f"{sms_sent} influencer{'s' if sms_sent > 1 else ''} notified by SMS"
    )
 
 
def _sms_payout_notification(influencer, total_commission, order_count):
    """SMS the influencer that their payout has gone out. Returns True if sent."""
    if not influencer.phone:
        return False
 
    phone = _format_sa_phone(influencer.phone)
    if not phone:
        return False
 
    message = (
        f"💰 {influencer.name.split()[0]}, your Marvelously Green commission "
        f"has been paid out! Total: R{total_commission:.2f} "
        f"covering {order_count} order{'s' if order_count > 1 else ''}. "
        f"Thank you for your amazing work! 🌿"
    )
 
    try:
        result = send_sms_smsportal(phone, message)
        return result.get('success', False)
    except Exception:
        return False



#Updated Django admin for Order, with shipping service columns and margin tracking.

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'price')
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    actions = [mark_commission_paid] 
    """
    Admin view for orders, showing shipping selection and margin per order.
    """
    
    list_display = (
        'id',
        'full_name',
        'status_badge',
        'amount_paid_display',
        'shipping_service_badge',     
        'pickup_point_display',        
        'shipping_service_badge',  
        'shipping_margin_display',  
        'courier_booked',           
        'tracking_number',         
        'date_ordered',
    )
    
    list_filter = (
        'status',
        'shipping_service_code',
        'pickup_point_code',   
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
        ('Shipping / Collection', {
            'fields': (
                'shipping_service_code',
                'shipping_service_name',
                'shipping_cost',
                'shipping_actual_cost',
                'shipping_margin_display',
                'pickup_point_code',       # NEW
                'courier_booked',
                'tracking_number',
                'shipped',
                'date_shipped',
            ),
            'description': (
                "For courier deliveries: book via Bob Go and fill in courier_booked + tracking_number. "
                "For collection orders: pickup_point_code tells you where the customer wants to collect. "
                "Mark as 'shipped' (with date_shipped) when the order is ready for collection — "
                "this triggers the 'ready for pickup' SMS."
            ),
        }),
    )
    inlines = [OrderItemInline]

    # ============================================
    # CUSTOM COLUMN: Pickup point display
    # ============================================
    def pickup_point_display(self, obj):
        if obj.shipping_service_code != 'collection':
            return mark_safe('<span style="color:#ccc;">—</span>')
        
        pickup_labels = {
            'office':       ('🏢', 'OFFICE',   '#2d5016'),
            'rrk_pharmacy': ('💊', 'RRK PHARM', '#c5a059'),
        }
        
        if obj.pickup_point_code in pickup_labels:
            icon, label, color = pickup_labels[obj.pickup_point_code]
            return format_html(
                '<span style="background:{}; color:white; padding:2px 7px; border-radius:8px; font-size:0.7rem; font-weight:700;">{} {}</span>',
                color, icon, label
            )
        
        return mark_safe('<span style="color:#999;">?</span>')
    pickup_point_display.short_description = 'Pickup'
    pickup_point_display.admin_order_field = 'pickup_point_code'

    
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
    
    # ============================================
    # UPDATED: shipping_service_badge to include Collection
    # ============================================
    def shipping_service_badge(self, obj):
        if not obj.shipping_service_code:
            return mark_safe('<span style="color:#999;">—</span>')
        
        colors = {
            'collection': ('#1b3022', 'COLLECT', '🏢'),
            'economy':    ('#c5a059', 'ECONOMY', '📮'),
            'standard':   ('#4CAF50', 'STANDARD', '📦'),
            'express':    ('#2d5016', 'EXPRESS', '⚡'),
        }
        color, label, icon = colors.get(
            obj.shipping_service_code,
            ('#999', obj.shipping_service_code.upper(), '?')
        )
        
        cost = f"R{obj.shipping_cost:.0f}" if obj.shipping_cost > 0 else 'FREE'
        return format_html(
            '<span style="background:{}; color:white; padding:2px 7px; border-radius:8px; font-size:0.7rem; font-weight:700;">{} {}</span> <small>{}</small>',
            color, icon, label, cost
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
    # BULK ACTIONS — add "mark as ready for pickup"
    # ============================================
    actions = ['mark_as_ready_for_pickup', 'mark_as_collected', 'mark_as_shipped']
    
    def mark_as_ready_for_pickup(self, request, queryset):
        """For Collection orders: mark as shipped + send SMS to customer."""
        collection_orders = queryset.filter(shipping_service_code='collection', status='paid')
        non_collection = queryset.exclude(shipping_service_code='collection')
        
        count = collection_orders.update(
            shipped=True,
            date_shipped=timezone.now(),
        )
        
        # TODO: integrate SMS sending here using your existing SMSPortal setup
        # for order in collection_orders:
        #     send_collection_ready_sms(order)
        
        msg = f"{count} collection order(s) marked as ready for pickup."
        if non_collection.exists():
            msg += f" {non_collection.count()} non-collection order(s) were skipped (use 'Mark as shipped' instead)."
        
        self.message_user(request, msg)
    mark_as_ready_for_pickup.short_description = "🏢 Mark as ready for pickup (Collection orders)"


    def mark_as_collected(self, request, queryset):
        """For Collection orders: mark as fully collected/delivered.""" 
        collection_orders = queryset.filter(shipping_service_code='collection')
        count = collection_orders.update(
            status='collected',  # add 'collected' to your STATUS choices
        )
        
        self.message_user(request, f"{count} collection order(s) marked as collected.")
    mark_as_collected.short_description = "✓ Mark as collected"
    
    
    def mark_as_shipped(self, request, queryset):
        """For courier orders only."""      
        courier_orders = queryset.exclude(shipping_service_code='collection')
        count = courier_orders.update(shipped=True, date_shipped=timezone.now())
        
        self.message_user(request, f"{count} courier order(s) marked as shipped.")
    mark_as_shipped.short_description = "📦 Mark as shipped (Courier orders)"