from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.conf import settings
from django.utils import timezone
from django.core.mail import send_mail

import datetime
import hashlib
import urllib.parse
import json
from decimal import Decimal
import requests
import logging

from cart.cart import Cart
from payment.forms import ShippingForm, PaymentForm
from payment.models import ShippingAddress, Order, OrderItem, PayfastPayment, CourierGuy
from .utils import send_sms_smsportal
from greenmarv.models import Product, Profile, DiscountCode, Influencer


logger = logging.getLogger(__name__)



def billing_info(request):
	if request.method == 'POST':
		# Initialize cart, product details, and calculate total weight and total amount
		cart = Cart(request)
		cart_products = cart.get_prods
		quantities = cart.get_quants
		total_after_discount = Decimal(request.session.get('total_after_discount', '0'))
		total_weight = cart.cart_weight()

		# Define collection address
		collection_address = {
			"type": "business",
			"company": "Green Marvel",
			"street_address": "620 Park Street",
			"local_area": "Arcadia",
			"city": "Pretoria",
			"zone": "Gauteng",
			"country": "ZA",
			"code": "0083",
			"lat": -25.444674,
			"lng": 28.131676
		}

		# Retrieve and set delivery address from session
		my_shipping = request.POST
		request.session['my_shipping'] = my_shipping
		if my_shipping:
			delivery_address = {
				"type": "residential",
				"company": my_shipping.get("shipping_full_name", ""),
				"street_address": my_shipping.get("shipping_address1", ""),
				"local_area": my_shipping.get("shipping_apartment", ""),
				"city": my_shipping.get("shipping_city", ""),
				"zone": my_shipping.get("shipping_province", ""),
				"country": my_shipping.get("shipping_country", "ZA"),
				"code": my_shipping.get("shipping_zipcode", ""),
				"lat": float(my_shipping.get("lat", -25.8066558)),
				"lng": float(my_shipping.get("lng", 28.334732))
			}
		else:
			messages.error(request, "Shipping address not found.")
			return redirect('cart_summary')

		# Define parcels based on cart items
		parcels = [
			{
				"submitted_length_cm": 20,
				"submitted_width_cm": 20,
				"submitted_height_cm": 20,
				"submitted_weight_kg": float(total_weight)
			}
		]

		# Check if free shipping applies
		total_items = len(cart)
		free_shipping_applies = False

		# Rule 1: Cart value >= R600
		if total_after_discount >= 600:
			free_shipping_applies = True

		# Rule 2: Festive promo – 3 or more products
		#if total_items >= 3:
		#	free_shipping_applies = True


		if free_shipping_applies:
			shipping_cost = Decimal(0)  # Free shipping
			total_with_shipping = total_after_discount
		else:
			# Prepare data payload for Shiplogic
			declared_value = float(total_after_discount)
			data = {
				"collection_address": collection_address,
				"delivery_address": delivery_address,
				"parcels": parcels,
				"declared_value": declared_value,
			}

			# Call send_delivery_request with the API details
			api_url = "https://api.shiplogic.com/v2/rates"  
			api_key = settings.COURIER_GUY_API_KEY 
			shiplogic_response = send_delivery_request(api_url, api_key, data)

			if shiplogic_response:
				# Extract rates and calculate shipping cost
				rates = []
				for rate in shiplogic_response.get("rates", []):
					formatted_rate = round(rate["rate"], 2)
					formatted_rate_excluding_vat = round(rate["rate_excluding_vat"], 2)

					delivery_date_from = rate["service_level"]["delivery_date_from"].split("T")[0]
					delivery_date_to = rate["service_level"]["delivery_date_to"].split("T")[0]

					rates.append({
						"rate": formatted_rate,
						"rate_excluding_vat": formatted_rate_excluding_vat,
						"service_level": rate["service_level"]["name"],
						"service_code": rate["service_level"]["code"],
						"delivery_date_from": delivery_date_from,
						"delivery_date_to": delivery_date_to,
						"extras": rate.get("extras", [])
					})
				shipping_cost = Decimal(shiplogic_response["rates"][0]["rate"]) if rates else Decimal(0)
				total_with_shipping = total_after_discount + shipping_cost

				# Store shipping and total information in the session
				request.session['shipping_cost'] = float(shipping_cost)
				request.session['total_with_shipping'] = float(total_with_shipping)

				# Pass data to the template
				return render(request, "payment/billing_info.html", {
					"cart_products": cart_products,
					"quantities": quantities,
					"totals": total_after_discount,
					"total_with_shipping": total_with_shipping,
					"shipping_info": my_shipping,
					"shipping_cost": shipping_cost,
					"rates": rates,
					"message": shiplogic_response.get("message", "No message")
				})

			else:
				messages.error(request, "Failed to retrieve shipping rates from Shiplogic.")
				return redirect("cart_summary")

		# If free shipping applies, pass data to the template
		request.session['shipping_cost'] = float(shipping_cost)
		request.session['total_with_shipping'] = float(total_with_shipping)
		return render(request, "payment/billing_info.html", {
			"cart_products": cart_products,
			"quantities": quantities,
			"totals": total_after_discount,
			"total_with_shipping": total_with_shipping,
			"shipping_info": my_shipping,
			"shipping_cost": shipping_cost,
			"rates": [],  # No rates since free shipping applies
			"message": "Free shipping applied!"
		})

	messages.error(request, "Invalid request method.")
	return redirect('index')


def send_delivery_request(api_url, api_key, data):
	try:
		headers = {"Content-Type": "application/json"}
		if api_key:
			headers["Authorization"] = f"Bearer {api_key}"

		response = requests.post(api_url, json=data, headers=headers)

		if response.status_code == 200:
			response_data = response.json()
			return response_data
		else:
			print(f"Error: API call failed with status code {response.status_code}")
			return None

	except requests.exceptions.RequestException as e:
		print(f"Error: {e}")
		return None


def checkout(request):
	# Get the cart
	cart = Cart(request)
	cart_products = cart.get_prods
	quantities = cart.get_quants
	total_weight = cart.cart_weight()

	# Retrieve discounted total from session
	discount_code = request.session.get('discount_code')
	#total_after_discount = cart.cart_total(discount_code=discount_code)
	total_after_discount = request.session.get('total_after_discount')
	

	if request.user.is_authenticated:
		# Checkout as logged in user
		# Shipping User
		shipping_user = ShippingAddress.objects.get(user__id=request.user.id)
		# Shipping Form
		shipping_form = ShippingForm(request.POST or None, instance=shipping_user)
		return render(request, "payment/checkout.html", {
			"cart_products":cart_products, 
			"quantities":quantities, 
			"total_weight":total_weight,
			"totals": total_after_discount, 
			"shipping_form":shipping_form, 
			'shipping_user': shipping_user 
			})
	else:
		# Checkout as guest
		shipping_form = ShippingForm(request.POST or None)
		return render(request, "payment/checkout.html", {
			"cart_products":cart_products, 
			"quantities":quantities, 
			"total_weight":total_weight,
			"totals": total_after_discount,  
			"shipping_form":shipping_form
			})


# ================================================================
# PROCESS ORDER — saves as pending_payment, redirects to Payfast
# ================================================================
def process_order(request):
	if not request.POST:
		return redirect('cart_summary')
 
	# Get the cart + session data
	cart = Cart(request)
	cart_products = cart.get_prods
	quantities = cart.get_quants
	total_after_discount = request.session.get('total_after_discount')
	total_with_shipping = request.session.get('total_with_shipping')
	my_shipping = request.session.get('my_shipping')
 
	if not my_shipping:
		messages.error(request, "Your shipping information has expired. Please try again.")
		return redirect('cart_summary')
 
	# Gather Order Info
	full_name = my_shipping['shipping_full_name']
	email = my_shipping['shipping_email']
	phone = my_shipping['shipping_phone']
 
	shipping_address = (
		f"{phone}\n{my_shipping['shipping_address1']}\n"
		f"{my_shipping.get('shipping_apartment', '')}\n"
		f"{my_shipping['shipping_city']}\n{my_shipping['shipping_province']}\n"
		f"{my_shipping['shipping_zipcode']}\n{my_shipping['shipping_country']}"
	)
 
	amount_paid = total_with_shipping
 
	# ============================================================
	# Create Order with status='pending_payment' (NOT confirmed yet)
	# ============================================================
	create_order = Order(
		full_name=full_name,
		email=email,
		phone=phone,
		shipping_address=shipping_address,
		amount_paid=amount_paid,
		status='pending_payment',  # <-- KEY CHANGE
	)
 
	if request.user.is_authenticated:
		create_order.user = request.user
	else:
		if not request.session.session_key:
			request.session.create()
		create_order.session_key = request.session.session_key
 
	create_order.save()
	order_id = create_order.pk
 
	# ============================================================
	# Create Order Items — unified for authenticated + guest
	# ============================================================
	user = request.user if request.user.is_authenticated else None
 
	for product in cart_products():
		price = product.sale_price if product.is_sale else product.price
 
		for key, value in quantities().items():
			if int(key) == product.id:
				OrderItem.objects.create(
					order_id=order_id,
					product_id=product.id,
					user=user,  # None for guests, which should be allowed at model level
					quantity=value,
					price=price,
				)
 
	# ============================================================
	# Create PayfastPayment record
	# ============================================================
	name_parts = create_order.full_name.strip().split()
	name_first = name_parts[0] if name_parts else ''
	name_last = name_parts[-1] if len(name_parts) > 1 else ''
 
	payment = PayfastPayment.objects.create(
		order_id=order_id,
		amount=amount_paid,
		status='Pending',
		name_first=name_first,
		name_last=name_last,
		email=email,
		phone=phone,
	)
 
	# ============================================================
	# Build Payfast payload
	# ============================================================
	data = {
		'merchant_id': settings.PAYFAST_MERCHANT_ID,
		'merchant_key': settings.PAYFAST_MERCHANT_KEY,
		'return_url': 'https://greenmarvelstore-production.up.railway.app/payment/payment_success/',  
		'cancel_url': 'https://greenmarvelstore-production.up.railway.app/payment/payment_cancel/',
		'notify_url': 'https://greenmarvelstore-production.up.railway.app/payment/payment_notify/',
 
		'name_first': payment.name_first,
		'name_last': payment.name_last,
		'email_address': payment.email,
 
		'm_payment_id': payment.order_id,
		'amount': payment.amount,
		'item_name': f'Green Marvel Order #{order_id}',
	}
 
	signature = generate_signature(data, settings.PAYFAST_PASSPHRASE)
	data['signature'] = signature
 
	payfast_url = "https://www.payfast.co.za/eng/process?"
	payment_url = payfast_url + urllib.parse.urlencode(data)
 
	# ============================================================
	# Clear cart from session ONLY — don't delete the Order yet
	# The order exists as pending_payment and waits for Payfast ITN
	# ============================================================
	if 'session_key' in request.session:
		del request.session['session_key']
 
	if request.user.is_authenticated:
		Profile.objects.filter(user__id=request.user.id).update(old_cart="")
 
	return redirect(payment_url)

# ================================================================
# PAYMENT_NOTIFY — the Payfast ITN webhook
# This is where the order becomes REAL
# ================================================================
@csrf_exempt
@require_POST
def payment_notify(request):
	"""
	Payfast ITN (Instant Transaction Notification) webhook.
	Called server-to-server by Payfast after payment succeeds/fails.
	This is the only reliable way to confirm payment.
	"""
	# Get all POST data
	post_data = request.POST.dict()
	logger.info(f"Payfast ITN received: {post_data}")
 
	# Extract critical fields
	payment_status = post_data.get('payment_status', '')
	order_id = post_data.get('m_payment_id', '')
	amount_gross = post_data.get('amount_gross', '0')
	pf_payment_id = post_data.get('pf_payment_id', '')
	signature_received = post_data.pop('signature', None)
 
	# ============================================================
	# Security step 1: Verify signature
	# ============================================================
	calculated_signature = generate_signature(post_data, settings.PAYFAST_PASSPHRASE)
	if signature_received != calculated_signature:
		logger.warning(f"Invalid Payfast signature for order {order_id}")
		return HttpResponse(status=400)
 
	# ============================================================
	# Security step 2: Get the order and verify amount
	# ============================================================
	try:
		order = Order.objects.get(id=order_id)
	except Order.DoesNotExist:
		logger.error(f"Payfast ITN for unknown order {order_id}")
		return HttpResponse(status=404)
 
	# Verify amount matches what we expected
	try:
		if abs(Decimal(amount_gross) - Decimal(str(order.amount_paid))) > Decimal('0.01'):
			logger.warning(
				f"Payfast amount mismatch for order {order_id}: "
				f"got R{amount_gross}, expected R{order.amount_paid}"
			)
			return HttpResponse(status=400)
	except Exception as e:
		logger.error(f"Error validating amount for order {order_id}: {e}")
		return HttpResponse(status=400)
 
	# ============================================================
	# Handle payment status
	# ============================================================
	if payment_status == 'COMPLETE':
		# Idempotency: only process if not already paid
		if order.status != 'paid':
			
			order.status = 'paid'
			order.date_paid = timezone.now()
			order.save()
 
			# Update PayfastPayment record
			PayfastPayment.objects.filter(order_id=order_id).update(
				status='Complete',
				pf_payment_id=pf_payment_id,
			)
 
			# Send notifications
			send_order_confirmation_sms(order)
			send_admin_order_alert_sms(order)
 
			logger.info(f"Order {order_id} confirmed as paid")
 
	elif payment_status == 'CANCELLED':
		order.status = 'cancelled'
		order.save()
		PayfastPayment.objects.filter(order_id=order_id).update(status='Cancelled')
		logger.info(f"Order {order_id} marked as cancelled")
 
	elif payment_status == 'FAILED':
		order.status = 'failed'
		order.save()
		PayfastPayment.objects.filter(order_id=order_id).update(status='Failed')
		logger.info(f"Order {order_id} marked as failed")
 
	return HttpResponse(status=200)


# ================================================================
# PAYMENT SUCCESS / CANCEL — user-facing landing pages
# These DON'T change order status (that's the webhook's job)
# ================================================================
def payment_success(request):
	"""User lands here after successful Payfast payment. Display-only."""
	return render(request, 'payment/payment_success.html')
 
 
def payment_cancel(request):
	"""User lands here if they cancel at Payfast."""
	return render(request, 'payment/payment_cancel.html')
 
 
# ================================================================
# SMS NOTIFICATION HELPERS
# ================================================================
def send_order_confirmation_sms(order):
	"""Send order confirmation SMS to the customer.""" 
	if not order.phone:
		logger.warning(f"No phone number for order {order.id}; skipping customer SMS")
		return
 
	# Format phone for SA (SMSPortal expects 27XXXXXXXXX format)
	phone = _format_sa_phone(order.phone)
	if not phone:
		logger.warning(f"Invalid phone format for order {order.id}: {order.phone}")
		return
 
	first_name = order.full_name.split()[0] if order.full_name else 'Customer'
 
	message = (
		f"Hi {first_name}, thank you for your Green Marvel order! "
		f"Order #{order.id} for R{order.amount_paid} has been confirmed. "
		f"We'll send you tracking info once your order ships. "
		f"🌿 Marvelously Green"
	)
 
	result = send_sms_smsportal(phone, message)
	if not result.get('success'):
		logger.error(f"Customer SMS failed for order {order.id}: {result}")
 
 

def send_admin_order_alert_sms(order):
	"""Alert admin that a new paid order has come in."""
	admin_phone = getattr(settings, 'ADMIN_SMS_PHONE', None)
	if not admin_phone:
		return  # Silently skip if not configured
 
	admin_phone = _format_sa_phone(admin_phone)
	if not admin_phone:
		return
 
	message = (
		f"🔔 New Green Marvel Order!\n"
		f"Order #{order.id}\n"
		f"Customer: {order.full_name}\n"
		f"Amount: R{order.amount_paid}\n"
		f"Phone: {order.phone}"
	)
 
	send_sms_smsportal(admin_phone, message)
 
 
def _format_sa_phone(phone):
	"""
	Convert South African phone number to SMSPortal format (27XXXXXXXXX).
	Accepts: 0831234567, +27831234567, 27831234567, 27 83 123 4567, etc.
	"""
	if not phone:
		return None
 
	# Strip all non-digit characters
	digits = ''.join(c for c in str(phone) if c.isdigit())
 
	if not digits:
		return None
 
	# Handle different SA formats
	if digits.startswith('27') and len(digits) == 11:
		return digits  # Already 27XXXXXXXXX
	elif digits.startswith('0') and len(digits) == 10:
		return '27' + digits[1:]  # 0XXXXXXXXX -> 27XXXXXXXXX
	elif len(digits) == 9:
		return '27' + digits  # XXXXXXXXX -> 27XXXXXXXXX
	else:
		return None  # Unknown format

#Generate Payfast Signature
def generate_signature(dataArray, passPhrase = ''):
	payload = ""
	for key in dataArray:
		# Get all the data from Payfast and prepare parameter string
		payload += key + "=" + urllib.parse.quote_plus(str(dataArray[key]).replace("+", " ")) + "&"
	# After looping through, cut the last & or append your passphrase
	payload = payload[:-1]
	if passPhrase != '':
		payload += f"&passphrase={passPhrase}"
	return hashlib.md5(payload.encode()).hexdigest()



# ================================================================
# CUSTOMER VIEW
# ================================================================
@login_required
def order_detail(request, pk):
	"""
	Customer-facing order detail page.
	A user can only view their OWN orders. Anyone trying to access
	another user's order gets a 404 (not a 403, so we don't leak existence).
	"""
	order = get_object_or_404(Order, id=pk, user=request.user)
	items = OrderItem.objects.filter(order=order.id)
 
	# Calculate subtotal (before shipping)
	subtotal = sum(item.price * item.quantity for item in items)
	shipping_cost = order.amount_paid - subtotal if order.amount_paid and subtotal else 0
 
	# Build timeline for visual progress
	timeline = _build_order_timeline(order)
 
	return render(request, 'payment/order_detail.html', {
		'order': order,
		'items': items,
		'subtotal': subtotal,
		'shipping_cost': shipping_cost,
		'timeline': timeline,
	})
 
 
def _build_order_timeline(order):
	"""Reusable timeline builder. Same logic as track_order."""
	timeline = [
		{
			'key': 'ordered', 'title': 'Order Placed',
			'description': 'Your order has been received',
			'icon': '📝', 'date': order.date_ordered,
			'completed': True, 'active': False,
		},
		{
			'key': 'paid', 'title': 'Payment Confirmed',
			'description': "We've received your payment",
			'icon': '💳', 'date': getattr(order, 'date_paid', None),
			'completed': order.status == 'paid', 'active': False,
		},
		{
			'key': 'processing', 'title': 'Processing',
			'description': "We're preparing your order",
			'icon': '📦', 'date': None,
			'completed': order.status == 'paid' and order.shipped,
			'active': order.status == 'paid' and not order.shipped,
		},
		{
			'key': 'shipped', 'title': 'Shipped',
			'description': 'Your order is on the way',
			'icon': '🚚', 'date': getattr(order, 'date_shipped', None),
			'completed': order.shipped,
			'active': order.shipped,
		},
		{
			'key': 'delivered', 'title': 'Delivered',
			'description': 'Enjoy your natural beauty products!',
			'icon': '💚', 'date': None,
			'completed': False, 'active': False,
		},
	]
 
	if order.status == 'cancelled':
		timeline = [
			timeline[0],
			{
				'key': 'cancelled', 'title': 'Order Cancelled',
				'description': 'This order was cancelled',
				'icon': '❌', 'date': None,
				'completed': True, 'active': True, 'cancelled': True,
			},
		]
 
	return timeline
 
 
# ================================================================
# ADMIN VIEW — improved version 
# ================================================================
def orders_admin(request, pk):
	"""Admin order management — superuser only."""
	if not (request.user.is_authenticated and request.user.is_superuser):
		messages.error(request, "Access Denied")
		return redirect('home')
 
	order = get_object_or_404(Order, id=pk)
	items = OrderItem.objects.filter(order=pk)
 
	# Calculate subtotal (before shipping)
	subtotal = sum(item.price * item.quantity for item in items)
	shipping_cost = order.amount_paid - subtotal if order.amount_paid and subtotal else 0
 
	if request.POST:
		status = request.POST.get('shipping_status', '')
 
		if status == "true":
			Order.objects.filter(id=pk).update(
				shipped=True,
				date_shipped=datetime.datetime.now()
			)
			messages.success(request, f"Order #{pk} marked as shipped")
			return redirect('shipped_dash')
		else:
			Order.objects.filter(id=pk).update(shipped=False)
			messages.success(request, f"Order #{pk} marked as not shipped")
			return redirect('not_shipped_dash')
 
	return render(request, 'payment/orders_admin.html', {
		"order": order,
		"items": items,
		"subtotal": subtotal,
		"shipping_cost": shipping_cost,
	})

# ================================================================
# ADMIN VIEWS — filter to only show PAID orders
# ================================================================
def orders(request, pk):
	if not (request.user.is_authenticated and request.user.is_superuser):
		messages.success(request, "Access Denied")
		return redirect('home')
 
	order = Order.objects.get(id=pk)
	items = OrderItem.objects.filter(order=pk)
 
	if request.POST:
		status = request.POST['shipping_status']
		if status == "true":
			import datetime
			Order.objects.filter(id=pk).update(shipped=True, date_shipped=datetime.datetime.now())
		else:
			Order.objects.filter(id=pk).update(shipped=False)
		messages.success(request, "Shipping Status Updated")
		return redirect('shipped_dash')
 
	return render(request, 'payment/orders.html', {"order": order, "items": items})
 
 
def not_shipped_dash(request):
	"""Only shows PAID orders that haven't shipped yet."""
	if not (request.user.is_authenticated and request.user.is_superuser):
		messages.success(request, "Access Denied")
		return redirect('home')
 
	# KEY CHANGE: only show orders that have been PAID
	orders = Order.objects.filter(status='paid', shipped=False)
 
	if request.POST:
		status = request.POST['shipping_status']
		num = request.POST['num']
		import datetime
		Order.objects.filter(id=num).update(shipped=True, date_shipped=datetime.datetime.now())
		messages.success(request, "Shipping Status Updated")
		return redirect('shipped_dash')
 
	return render(request, "payment/not_shipped_dash.html", {"orders": orders})
 
 
def shipped_dash(request):
	"""Only shows PAID orders that have shipped."""
	if not (request.user.is_authenticated and request.user.is_superuser):
		messages.success(request, "Access Denied")
		return redirect('home')
 
	orders = Order.objects.filter(status='paid', shipped=True)
 
	if request.POST:
		num = request.POST['num']
		Order.objects.filter(id=num).update(shipped=False)
		messages.success(request, "Shipping Status Updated")
		return redirect('not_shipped_dash')
 
	return render(request, "payment/shipped_dash.html", {"orders": orders})


#Process Order and Initiate Payfast payment
def process_order2(request):
	if request.POST:
		# Get the cart
		cart = Cart(request)
		cart_products = cart.get_prods
		quantities = cart.get_quants
		
		total_after_discount = request.session.get('total_after_discount')
		
		total_with_shipping = request.session.get('total_with_shipping')

		# Get Billing Info from the last page
		payment_form = PaymentForm(request.POST or None)
	
		# Get Shipping Session Data
		my_shipping = request.session.get('my_shipping')

		# Gather Order Info
		full_name = my_shipping['shipping_full_name']
		email = my_shipping['shipping_email']
		phone = my_shipping['shipping_phone']

		# Create Shipping Address from session info
		shipping_address = f"{my_shipping['shipping_phone']}\n{my_shipping['shipping_address1']}\n{my_shipping['shipping_apartment']}\n{my_shipping['shipping_city']}\n{my_shipping['shipping_province']}\n{my_shipping['shipping_zipcode']}\n{my_shipping['shipping_country']}"

		amount_paid = total_with_shipping

		#user = request.user
		# Create Order
		create_order = Order(full_name=full_name, email=email, shipping_address=shipping_address, amount_paid=amount_paid)
		
		if request.user.is_authenticated:
			create_order.user = request.user
		else:
			if not request.session.session_key:
				request.session.create()
			create_order.session_key = request.session.session_key
		
		create_order.save()

		# Get the order ID
		order_id = create_order.pk
		create_order.save()
			
		
		if request.user.is_authenticated:
			# logged in			
			user = request.user
			
			# Get product Info
			for product in cart_products():
				# Get product ID
				product_id = product.id
				# Get product price
				if product.is_sale:
					price = product.sale_price
				else:
					price = product.price

				# Get quantity
				for key,value in quantities().items():
					if int(key) == product.id:
						# Create order item
						create_order_item = OrderItem(order_id=order_id, product_id=product_id, user=user, quantity=value, price=price)
						create_order_item.save()


			payment = PayfastPayment.objects.create(
				order_id=order_id,
				amount=amount_paid,
				status='Pending',
				name_first = create_order.full_name.split()[0],
				name_last = create_order.full_name.split()[-1],
				email = create_order.email,
				phone = phone,
				)

			data = {
				'merchant_id': settings.PAYFAST_MERCHANT_ID,
				'merchant_key': settings.PAYFAST_MERCHANT_KEY,
				#'return_url': 'http://127.0.0.1:8000/payment/payment_success/', 
				'return_url': 'https://greenmarvelstore-production.up.railway.app/payment/payment_success/',   
				'cancel_url': 'https://greenmarvelstore-production.up.railway.app/payment/payment_cancel/',
				'notify_url': 'https://greenmarvelstore-production.up.railway.app/payment/payment_notify/',

				'name_first': payment.name_first, 
				'name_last': payment.name_last, 
				'email_address': payment.email,
				
				'm_payment_id': payment.order_id,
				'amount': payment.amount,
				'item_name': 'Order Product',
				}
			signature = generate_signature(data, settings.PAYFAST_PASSPHRASE)
			data['signature'] = signature

			payfast_url =  "https://www.payfast.co.za/eng/process?" 
			
			payment_url = payfast_url + urllib.parse.urlencode(data)

			# Clear the cart
			for key in list(request.session.keys()):
				if key == "session_key":
					del request.session[key]

			if user:
				current_user = Profile.objects.filter(user__id=request.user.id)
				current_user.update(old_cart="")


			return redirect(payment_url)			

		else:			
			# Get product Info
			for product in cart_products():
				# Get product ID
				product_id = product.id
				# Get product price
				if product.sale:
					price = product.sale_price
				else:
					price = product.price

				# Get quantity
				for key,value in quantities().items():
					if int(key) == product.id:
						# Create order item
						create_order_item = OrderItem(order_id=order_id, product_id=product_id, quantity=value, price=price)
						create_order_item.save()

			payment = PayfastPayment.objects.create(
				order_id=order_id,
				amount=amount_paid,
				status='Pending',
				name_first = create_order.full_name.split()[0],
				name_last = create_order.full_name.split()[-1],
				email = create_order.email,
				phone = phone,
			)

			data = {
				'merchant_id': settings.PAYFAST_MERCHANT_ID,
				'merchant_key': settings.PAYFAST_MERCHANT_KEY,
				#'return_url': 'http://127.0.0.1:8000/payment/payment_success/', 
				'return_url': 'http://127.0.0.1:8000/payment/payment_success/', #'https://greenmarvelstore-production.up.railway.app/payment/payment_success/',  
				'cancel_url': 'http://127.0.0.1:8000/payment/payment_cancel/', #'https://greenmarvelstore-production.up.railway.app/payment/payment_cancel/',
				'notify_url': 'http://127.0.0.1:8000/payment/payment_notify/', #'https://greenmarvelstore-production.up.railway.app/payment/payment_notify/',

				'name_first': payment.name_first,  
				'name_last':  payment.name_last,   
				'email_address': payment.email,         	

				'm_payment_id': payment.order_id,
				'amount': payment.amount,
				'item_name': 'Order Product',
				}
			signature = generate_signature(data, settings.PAYFAST_PASSPHRASE)
			data['signature'] = signature

			payfast_url =  "https://sandbox.payfast.co.za/eng/process?" #"https://www.payfast.co.za/eng/process?"
			payment_url = payfast_url + urllib.parse.urlencode(data)

			# Clear the cart
			for key in list(request.session.keys()):
				if key == "session_key":
					del request.session[key]

			return redirect(payment_url)
			


# Admin View
def not_shipped_dash2(request):
	if request.user.is_authenticated and request.user.is_superuser:
		orders = Order.objects.filter(shipped=False)
		if request.POST:
			status = request.POST['shipping_status']
			num = request.POST['num']
			# Get the order
			order = Order.objects.filter(id=num)
			# grab Date and time
			now = datetime.datetime.now()
			# update order
			order.update(shipped=True, date_shipped=now)
			# redirect
			messages.success(request, "Shipping Status Updated")
			return redirect('shipped_dash')

		return render(request, "payment/not_shipped_dash.html", {"orders":orders})
		
	else:
		messages.success(request, "Access Denied")
		return redirect('home')


#For Admin View
def shipped_dash2(request):
	if request.user.is_authenticated and request.user.is_superuser:
		orders = Order.objects.filter(shipped=True)
		if request.POST:
			status = request.POST['shipping_status']
			num = request.POST['num']
			# grab the order
			order = Order.objects.filter(id=num)
			# grab Date and time
			now = datetime.datetime.now()
			# update order
			order.update(shipped=False)
			# redirect
			messages.success(request, "Shipping Status Updated")
			return redirect('not_shipped_dash')

		return render(request, "payment/shipped_dash.html", {"orders":orders})
	else:
		messages.success(request, "Access Denied")
		return redirect('home')


#For Admin View
def successful_payments(request):
	if request.user.is_authenticated and request.user.is_superuser:
		# Retrieve all successful payments (assuming status 'COMPLETE' indicates success)
		successful_payments = PayfastPayment.objects.filter(status='COMPLETE')

		# Pass the successful payments to the template
		#context = {
		#'successful_payments': successful_payments,
		#}

		return render(request, 'payment/successful_payments.html', {
			'successful_payments': successful_payments,
			})




@csrf_exempt
def payment_notify2(request):
	if request.method == 'POST':
		data = request.POST.dict()
		received_signature = data.pop('signature', None)
		generated_signature = generate_signature(data, settings.PAYFAST_PASSPHRASE)


		if generated_signature == received_signature:
			payment_status = data.get('payment_status')
			order_id = data.get('m_payment_id')

			try:
				payment = PayfastPayment.objects.get(order_id=order_id)

				if payment_status == 'COMPLETE':
					payment.status = 'Completed'
					
				else:
					payment.status = 'Failed'
					
				payment.itn_payload = request.POST.urlencode()
				payment.save()
				

				# Optionally, store order_id and amount_paid in session for success view
				#request.session['order_id'] = order_id
				#request.session['amount_paid'] = payment.amount_paid
				#request.session['itn_payload'] = request.POST.urlencode()

				return HttpResponse('Payment notification processed', status=200)

			except (Payment.DoesNotExist, Order.DoesNotExist):
				return HttpResponse('Order or payment not found', status=400)

		else:
			return HttpResponse('Signature mismatch', status=400)

	return HttpResponse('Invalid request method', status=400)


def notify_influencer(influencer, total_before_discount, discount_percentage, total_after_discount, discount_code, commission_rate, commission):
	subject = "Your Discount Code Was Used!"
	message = (
		f"Hello {influencer.name}, \n\n"
		f"Your discount code: {discount_code}, was used for a purchase of R{total_before_discount}. "
		f"The customer received a {discount_percentage}% discount.\n"
		f"Which reduced their order to R{total_after_discount} .\n\n"
		f"At the commission rate of: {commission_rate}%."
		f"Your commission for this order is: R{commission}.\n"
		f"Thank you for your contribution!.\n\n"
		f"Regards,\n"
		f"The Green Marvel Sales Team"
		)

	send_mail(
		subject,
		message,
		settings.EMAIL_HOST_USER,  # Replace with your store's email
		[influencer.email],
		fail_silently=False,
	)



def payment_cancel2(request):
	return render(request, 'payment/payment_cancel.html')




def payment_success2(request):
	'''discount_code = request.session['discount_code']
	
	discount = DiscountCode.objects.get(code=discount_code, is_active=True)

	# Retrieve the total amount before the discount
	total_before_discount = discount.total_before_discount
	
	if discount.influencer:
		# Retrieve discounted total from session
		discount_code = request.session.get('discount_code')
		#total_after_discount = cart.cart_total(discount_code=discount_code)
		total_after_discount = request.session.get('total_after_discount')
		#totals = request.session.get('totals')

		commission = request.session.get('commission')
		commission_rate = discount.influencer.commission_rate		


		# Notify the influencer
		notify_influencer(discount.influencer, total_before_discount, 
							discount.discount_percentage, total_after_discount, 
								discount_code, commission_rate, commission)'''
	
	return render(request, "payment/payment_success.html", {})



def order_history(request):
	if request.user.is_authenticated:
		orders = Order.objects.filter(user=request.user).order_by('-date_ordered')
	else:
		session_key = request.session.session_key
		if not session_key:
			request.session.create()  # generate a session key
			session_key = request.session.session_key
		orders = Order.objects.filter(session_key=session_key).order_by('-date_ordered')

	return render(request, 'payment/order_history.html', {'orders': orders})


def order_history2(request):
	user_orders = Order.objects.filter(user=request.user).order_by('-date_ordered')
	return render(request, 'payment/order_history.html', {'orders': user_orders})


def track_order(request):
	order = None
	items = []
	timeline = []
	tracking_error = None
	
	order_id_param = request.GET.get('order_id', '')
	email_param = request.GET.get('email', '')
	
	if request.method == 'POST' or (order_id_param and email_param):
		# ... lookup logic ...
	
		return render(request, 'payment/track_order.html', {...})

@login_required
def track_order2(request, order_id):
	try:
		order = Order.objects.get(id=order_id, customer=request.user)
		tracking_events = order.tracking_events.order_by('timestamp')

		# Fetch current status from the courier API (optional)
		# Example: tracking_info = get_tracking_info(order.tracking_number)

		return render(request, "payment/track_order.html", {
			"order": order,
			"tracking_events": tracking_events,
			"current_status": order.shipment_status,  # Optional from API
		})
	except Order.DoesNotExist:
		messages.error(request, "Order not found.")
		return redirect('order_history')







