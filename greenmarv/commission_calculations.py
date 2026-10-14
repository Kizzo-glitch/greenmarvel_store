
from decimal import Decimal

from payment.models import Order


PAID_STATUSES = ('paid', 'dispatched', 'in_transit', 'delivered', 'collected')
 
 
def _calculate_pending_commission(influencer):
    """Total commission owed but not yet paid out."""
    orders = Order.objects.filter(
        influencer=influencer,
        status__in=PAID_STATUSES,
        commission_paid_out_at__isnull=True,
    ).prefetch_related('orderitem_set')
 
    total = Decimal('0.00')
    for order in orders:
        subtotal = sum(
            item.price * item.quantity
            for item in order.orderitem_set.all()
        )
        total += subtotal * Decimal(str(influencer.commission_rate)) / Decimal('100')
    return total.quantize(Decimal('0.01'))
 
 
def _calculate_paid_commission(influencer):
    """Total commission that's been paid out."""
    orders = Order.objects.filter(
        influencer=influencer,
        status__in=PAID_STATUSES,
        commission_paid_out_at__isnull=False,
    ).prefetch_related('orderitem_set')
 
    total = Decimal('0.00')
    for order in orders:
        subtotal = sum(
            item.price * item.quantity
            for item in order.orderitem_set.all()
        )
        total += subtotal * Decimal(str(influencer.commission_rate)) / Decimal('100')
    return total.quantize(Decimal('0.01'))
 