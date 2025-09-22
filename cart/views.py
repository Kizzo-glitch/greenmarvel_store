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



def cart_summary(request):
	cart = Cart(request)
	cart_products = cart.get_prods
	quantities = cart.get_quants
	totals = cart.cart_total()

	discount_amount = Decimal(0)
	total_after_discount = totals
	commission = Decimal(0)
	applied_promo = None

	# ----- 1) Check if a discount code is posted -----
	discount_code = None
	if request.method == "POST" and 'discount_code' in request.POST:
		discount_code = request.POST.get('discount_code')
		try:
			discount = DiscountCode.objects.get(code=discount_code, is_active=True)
			# normal percentage discount
			discount_amount = (
				Decimal(discount.discount_percentage) / 100 * totals
			).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
			total_after_discount = (totals - discount_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

			if discount.influencer:
				commission = (
					Decimal(discount.influencer.commission_rate) / 100 * totals
				).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

		except ObjectDoesNotExist:
			messages.error(request, "Invalid discount code")

	# ----- 2) Check Heritage Day promo (only if no code used) -----
	else:
		try:
			heritage = Promotion.objects.get(name="Heritage Day Buy 3")
		except Promotion.DoesNotExist:
			heritage = None

		if heritage and heritage.is_running():
			# Count total quantity of items
			total_qty = sum(quantities.values())
			if total_qty >= 3:
				# Find the cheapest unit price in the cart
				cheapest_price = min(p.price for p in cart_products)
				discount_amount = Decimal(cheapest_price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
				total_after_discount = (totals - discount_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
				applied_promo = "Heritage Day: Cheapest Item Free"

	# Save to session if needed for checkout
	request.session['total_after_discount'] = str(total_after_discount)
	request.session['commission'] = str(commission)
	request.session['discount_code'] = discount_code
	request.session['heritage_promo'] = applied_promo

	return render(request, "cart_summary.html", {
		"cart_products": cart_products,
		"quantities": quantities,
		"totals": totals,
		"discount_amount": discount_amount,
		"total_after_discount": total_after_discount,
		"commission": commission,
		"applied_promo": applied_promo,
	})


def cart_summary(request):
	cart = Cart(request)
	cart_products = cart.get_prods
	quantities = cart.get_quants
	totals = cart.cart_total()

	discount_amount = Decimal(0)
	total_after_discount = totals
	commission = Decimal(0)
	discount_code = None

	if request.method == "POST" and 'discount_code' in request.POST:
		discount_code = request.POST.get('discount_code')

		try:
			discount = DiscountCode.objects.get(code=discount_code, is_active=True)

			# Determine discount amount
			if discount.amount_off:
				discount_amount = Decimal(discount.amount_off).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
			elif discount.discount_percentage:
				discount_amount = (Decimal(discount.discount_percentage) / 100 * totals).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

			# Cap discount to total to avoid negative values
			discount_amount = min(discount_amount, totals)

			total_after_discount = (totals - discount_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

			# Save the total before the discount
			discount.total_before_discount = totals
			discount.save()

			# Influencer commission (if linked)
			if discount.influencer:
				commission = (Decimal(discount.influencer.commission_rate) / 100 * totals).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

		except ObjectDoesNotExist:
			messages.error(request, "Invalid discount code")

	# Store values in session
	request.session['total_after_discount'] = str(total_after_discount)
	request.session['commission'] = str(commission)
	request.session['discount_code'] = discount_code

	return render(request, "cart_summary.html", {
		"cart_products": cart_products, 
		"quantities": quantities, 
		"totals": totals, 
		"discount_amount": discount_amount,
		"total_after_discount": total_after_discount,
		"commission": commission,
	})


def cart_summary2(request):
	# Get the cart
	cart = Cart(request)
	cart_products = cart.get_prods
	quantities = cart.get_quants
	totals = cart.cart_total()

	discount_amount = Decimal(0)
	total_after_discount = totals
	commission = Decimal(0)
	

	# Check if a discount code has been applied
	if request.method == "POST" and 'discount_code' in request.POST:
		discount_code = request.POST.get('discount_code').strip().upper()
		
		# Validate the discount code (assuming you have a Discount model)
		try:
			discount = DiscountCode.objects.get(code=discount_code, is_active=True)
			
			# Apply the discount (assumes percentage-based discount)
			discount_amount = (Decimal(discount.discount_percentage / 100) * totals).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
			total_after_discount = (totals - discount_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

			# Save the total before the discount
			discount.total_before_discount = totals
			discount.save()

			# Calculate influencer commission (assuming you store influencer info in the discount model)
			if discount.influencer:
				commission = (Decimal((discount.influencer.commission_rate) / 100) * totals).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
				commission_rate = discount.influencer.commission_rate


				# Notify the influencer
				#notify_influencer(discount.influencer, totals, discount.discount_percentage, total_after_discount, discount_code, commission_rate, commission)

		except ObjectDoesNotExist:
			# Handle invalid discount code
			messages.error(request, "Invalid discount code")

	# Store the Total and Influencer's commition after discount in the session to be accessed 
	request.session['total_after_discount'] = str(total_after_discount)
	#request.session['totals'] = str(totals)

	request.session['commission'] = str(commission)
	request.session['discount_code'] = discount_code if 'discount_code' in request.POST else None

	return render(request, "cart_summary.html", {
		"cart_products": cart_products, 
		"quantities": quantities, 
		"totals": totals, 
		"discount_amount": discount_amount,
		"total_after_discount": total_after_discount,
		"commission": commission,
	})


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