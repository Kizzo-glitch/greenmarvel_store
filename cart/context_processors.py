from .cart import Cart
from .views import _calc_free_shipping, FREE_SHIPPING_THRESHOLD

# Create context processor so our cart can work on all pages of the site
def cart(request):
	# Return the default data from our Cart
	return {'cart': Cart(request)}



def free_shipping(request):
    """Make free shipping info available in ALL templates."""
    cart = Cart(request)
    cart_total = cart.cart_total()
    
    # Try to use the discounted total from session if available
    total = request.session.get('total_after_discount')
    if total:
        from decimal import Decimal
        total = Decimal(total)
    else:
        total = cart_total
    
    amount_needed, qualifies, progress = _calc_free_shipping(total)
    
    return {
        'global_free_shipping_threshold': FREE_SHIPPING_THRESHOLD,
        'global_amount_needed_for_free_shipping': amount_needed,
        'global_qualifies_for_free_shipping': qualifies,
        'global_free_shipping_progress_pct': progress,
    }