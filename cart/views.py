from django.shortcuts import render, get_object_or_404
from .cart import Cart
from greenmarv.models import Product
from django.http import JsonResponse
from django.contrib import messages

from greenmarv.models import DiscountCode, Influencer
from django.core.mail import send_mail
import json
from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings

from .models import Promotion

from django.utils import timezone



# ============================================
# Free shipping threshold — single source of truth
# ============================================
FREE_SHIPPING_THRESHOLD = Decimal('600.00')


def _calc_free_shipping(total):
    """
    Returns a tuple: (amount_needed, qualifies, progress_pct)
    All values calculated cleanly so the template just displays them.
    """
    total = Decimal(str(total))
    if total >= FREE_SHIPPING_THRESHOLD:
        return Decimal('0.00'), True, 100
    
    amount_needed = (FREE_SHIPPING_THRESHOLD - total).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )
    
    # Progress percentage (0-100)
    progress_pct = int((total / FREE_SHIPPING_THRESHOLD) * 100)
    
    return amount_needed, False, progress_pct


def cart_summary(request):
    cart = Cart(request)
    cart_products = cart.get_prods
    quantities = cart.get_quants

    # Initialize ALL variables upfront — prevents UnboundLocalError edge cases
    base_total = cart.cart_total()
    discount_amount = Decimal('0.00')
    total_after_discount = base_total  # Default: no discount applied
    commission = Decimal('0.00')
    applied_promo = None
    discount_code = None

    # ============================================
    # Step 1: Check POST for discount code
    # ============================================
    if request.method == "POST" and 'discount_code' in request.POST:
        discount_code = request.POST.get('discount_code', '').strip()
        try:
            discount = DiscountCode.objects.get(code=discount_code, is_active=True)
            
            discount_amount = (
                Decimal(discount.discount_percentage) / 100 * base_total
            ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            total_after_discount = (base_total - discount_amount).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )

            if discount.influencer:
                commission = (
                    Decimal(discount.influencer.commission_rate) / 100 * base_total
                ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            applied_promo = f"Code: {discount.code}"
            messages.success(request, f"Discount code '{discount.code}' applied!")

        except ObjectDoesNotExist:
            messages.error(request, "Invalid discount code")
            # total_after_discount already defaults to base_total — no change needed

    # ============================================
    # Step 2: Heritage Day promo (only if no discount code POST)
    # ============================================
    else:
        try:
            heritage_special = Promotion.objects.get(
                name="Heritage Day Buy 3", is_active=True
            )
        except Promotion.DoesNotExist:
            heritage_special = None

        if heritage_special:
            heritage_total = cart.heritage_total()
            total_after_discount = heritage_total.quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            applied_promo = "Heritage Day: Cheapest Item Free"
        # else: total_after_discount stays at base_total (already set above)

    # ============================================
    # Step 3: Calculate free-shipping nudge
    # Based on total_after_discount (post-discount), so a customer who
    # discounted their way below R600 doesn't get free shipping
    # ============================================
    amount_needed_for_free_shipping, qualifies_for_free_shipping, free_shipping_progress_pct = \
        _calc_free_shipping(total_after_discount)

    # ============================================
    # Step 4: Save key values to session
    # ============================================
    request.session['total_after_discount'] = str(total_after_discount)
    request.session['commission'] = str(commission)
    request.session['discount_code'] = discount_code
    request.session['applied_promo'] = applied_promo

    # ============================================
    # Step 5: Render
    # ============================================
    return render(
        request,
        "cart_summary.html",
        {
            "cart_products": cart_products,
            "quantities": quantities,
            "base_total": base_total,
            "discount_amount": discount_amount,
            "total_after_discount": total_after_discount,
            "commission": commission,
            "applied_promo": applied_promo,
            # Free shipping context
            "free_shipping_threshold": FREE_SHIPPING_THRESHOLD,
            "amount_needed_for_free_shipping": amount_needed_for_free_shipping,
            "qualifies_for_free_shipping": qualifies_for_free_shipping,
            "free_shipping_progress_pct": free_shipping_progress_pct,
        },
    )


def cart_summary2(request):
	cart = Cart(request)
	cart_products = cart.get_prods
	quantities = cart.get_quants

	discount_amount = Decimal('0.00')
	total_after_discount = Decimal('0.00')
	commission = Decimal('0.00')
	applied_promo = None
	discount_code = None

	# ---- Step 1: Check POST for discount code ----
	if request.method == "POST" and 'discount_code' in request.POST:
		discount_code = request.POST.get('discount_code').strip()
		try:
			discount = DiscountCode.objects.get(code=discount_code, is_active=True)
			base_total = cart.cart_total()
			discount_amount = (
				Decimal(discount.discount_percentage) / 100 * base_total
			).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
			total_after_discount = (base_total - discount_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

			if discount.influencer:
				commission = (
					Decimal(discount.influencer.commission_rate) / 100 * base_total
				).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

			applied_promo = f"Code: {discount.code}"

		except ObjectDoesNotExist:
			messages.error(request, "Invalid discount code")
			base_total = cart.cart_total()
			total_after_discount = base_total

	# ---- Step 2: Heritage Day promo (only if no discount code used) ----
	else:
		base_total = cart.cart_total()
		try:
			heritage_special = Promotion.objects.get(name="Heritage Day Buy 3", is_active=True)
		except Promotion.DoesNotExist:
			heritage_special = None

		if heritage_special:
			# Use heritage total and set applied promo
			heritage_total = cart.heritage_total()
			total_after_discount = heritage_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
			applied_promo = "Heritage Day: Cheapest Item Free"
		else:
			total_after_discount = base_total

	# ---- Step 3: Save key values to session ----
	request.session['total_after_discount'] = str(total_after_discount)
	request.session['commission'] = str(commission)
	request.session['discount_code'] = discount_code
	request.session['applied_promo'] = applied_promo

	# ---- Step 4: Render ----
	return render(
		request,
		"cart_summary.html",
		{
			"cart_products": cart_products,
			"quantities": quantities,
			"base_total": base_total,
			"discount_amount": discount_amount,
			"total_after_discount": total_after_discount,
			"commission": commission,
			"applied_promo": applied_promo,
		},
	)




def notify_influencer(influencer, totals, discount_percentage, total_after_discount, discount_code, commission_rate, commission):
	subject = "Your Discount Code Was Used!"
	message = (
		f"Hello {influencer.name}, \n\n"
		f"Your discount code: {discount_code}, was used for a purchase of R{totals:.2f}. "
		f"The customer received a {discount_percentage}% discount.\n"
		f"Which reduced their order to R{total_after_discount} .\n"
		f"At the commission rate of: {commission_rate}%.\n"
		f"Your commission for this order is: R{commission:.2f}.\n"
		f"Thank you for your contribution!.\n"
		f"Green Marvel Sales Team"
		)

	send_mail(
		subject,
		message,
		settings.EMAIL_HOST_USER,  # Replace with your store's email
		[influencer.email],
		fail_silently=False,
	)


def cart_add(request):
	# Get the Cart
	cart = Cart(request)

	# Test for POST
	if request.POST.get('action') == 'post':
		# Get product
		product_id = int(request.POST.get('product_id'))
		product_qty = int(request.POST.get('product_qty'))
		
		# Loock up product in DB
		product = get_object_or_404(Product, id=product_id)

		# Save to a session
		cart.add(product=product, quantity=product_qty)

		# Get Cart Quantity
		cart_quantity = cart.__len__()

		# Return a response
		#response = JsonResponse({'Product Name: ': product.name})
		
		response = JsonResponse({'qty': cart_quantity})
		messages.success(request, ("Item Added to Cart..... Click Cart to see added products"))
		return response



def cart_delete(request):
	cart = Cart(request)
	if request.POST.get('action') == 'post':
		# Get stuff
		product_id = int(request.POST.get('product_id'))
		# Call delete Function in Cart
		cart.delete(product=product_id)

		response = JsonResponse({'product':product_id})
		#return redirect('cart_summary')
		messages.success(request, ("Item Deleted From Shopping Cart..."))
		return response



def cart_update(request):
	cart = Cart(request)
	if request.POST.get('action') == 'post':
		# Get stuff
		product_id = int(request.POST.get('product_id'))
		product_qty = int(request.POST.get('product_qty'))

		cart.update(product=product_id, quantity=product_qty)

		response = JsonResponse({'qty':product_qty})
		#return redirect('cart_summary')
		messages.success(request, ("Your Cart Has Been Updated..."))
		return response