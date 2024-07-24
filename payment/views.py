from django.shortcuts import render, redirect, get_object_or_404
#from django.contrib.auth.decorators import login_required

from cart.cart import Cart
from payment.forms import ShippingForm, PaymentForm
from payment.models import ShippingAddress, Order, OrderItem, PayfastPayment
from django.contrib.auth.models import User
from django.contrib import messages
from greenmarv.models import Product, Profile
import datetime

from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
import hashlib
import urllib.parse
from django.conf import settings





def orders(request, pk):
	if request.user.is_authenticated and request.user.is_superuser:
		# Get the order
		order = Order.objects.get(id=pk)
		# Get the order items
		items = OrderItem.objects.filter(order=pk)

		if request.POST:
			status = request.POST['shipping_status']
			# Check if true or false
			if status == "true":
				# Get the order
				order = Order.objects.filter(id=pk)
				# Update the status
				now = datetime.datetime.now()
				order.update(shipped=True, date_shipped=now)
			else:
				# Get the order
				order = Order.objects.filter(id=pk)
				# Update the status
				order.update(shipped=False)
			messages.success(request, "Shipping Status Updated")
			return redirect('home')

		return render(request, 'payment/orders.html', {"order":order, "items":items})

	else:
		messages.success(request, "Access Denied")
		return redirect('home')


#For Admin View
def not_shipped_dash(request):
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
			return redirect('home')

		return render(request, "payment/not_shipped_dash.html", {"orders":orders})
		
	else:
		messages.success(request, "Access Denied")
		return redirect('home')

#For Admin View
def shipped_dash(request):
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
			return redirect('home')

		return render(request, "payment/shipped_dash.html", {"orders":orders})
	else:
		messages.success(request, "Access Denied")
		return redirect('home')

#For Admin View
def payment_success(request):
	if request.user.is_authenticated and request.user.is_superuser:
		order_id = request.session.get('order_id')
		amount_paid = request.session.get('amount_paid')
		itn_payload = request.session.get('itn_payload')

		request.session.pop('order_id', None)
		request.session.pop('amount_paid', None)
		request.session.pop('itn_payload', None)

		itn_data = dict(urllib.parse.parse_qsl(itn_payload)) if itn_payload else {}
    
		return render(request, 'payment/payment_success.html', {
        	'order_id': order_id,
        	'amount_paid': amount_paid,
        	'itn_data': itn_data,
    	})


@csrf_exempt
def payment_notify(request):
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


#Process Order and Initiate Payfast payment
def process_order(request):
	if request.POST:
		# Get the cart
		cart = Cart(request)
		cart_products = cart.get_prods
		quantities = cart.get_quants
		totals = cart.cart_total()

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
		amount_paid = totals

		#user = request.user
		# Create Order
		#create_order = Order(user=user, full_name=full_name, email=email, shipping_address=shipping_address, amount_paid=amount_paid)
		#create_order.save()

			
		
		
		if request.user.is_authenticated:
			# logged in			
			user = request.user
			# Add order items	
			# Create Order			
			create_order = Order(user=user, full_name=full_name, email=email, shipping_address=shipping_address, amount_paid=amount_paid)
			# Get the order ID
			order_id = create_order.pk
			create_order.save()
			
			
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
						create_order_item = OrderItem(order_id=order_id, product_id=product_id, user=user, quantity=value, price=price)
						create_order_item.save()


			payment = PayfastPayment.objects.create(
            	order_id=order_id,
            	amount=amount_paid,
            	status='Pending',
            	name_first = user.first_name,
	        	name_last = user.last_name,
	        	email = create_order.email,
	        	phone = phone,
	        	)

			data = {
            	'merchant_id': settings.PAYFAST_MERCHANT_ID,
            	'merchant_key': settings.PAYFAST_MERCHANT_KEY,
            	'return_url': 'https://greenmarvelstore-production.up.railway.app/home/',  
            	'cancel_url': 'https://greenmarvelstore-production.up.railway.app/payment/payment_cancel/',
            	'notify_url': 'https://greenmarvelstore-production.up.railway.app/payment/payment_notify/',

            	'name_first': payment.name_first, #full_name.split()[0],  # Assuming first name is the first part of full_name
            	'name_last': payment.name_last, #full_name.split()[-1],  # Assuming last name is the last part of full_name
            	'email_address': payment.email,
            	'cell_number': payment.phone,

            	'm_payment_id': payment.order_id,
            	'amount': payment.amount,
            	'item_name': 'Order Product',
            	}
			signature = generate_signature(data, settings.PAYFAST_PASSPHRASE)
			data['signature'] = signature

			payfast_url = "https://sandbox.payfast.co.za/eng/process?"
			#payment_url = payfast_url + urllib.parse.urlencode(data).replace('%2B', '+')
			payment_url = payfast_url + urllib.parse.urlencode(data)

			# Clear the cart
			for key in list(request.session.keys()):
				if key == "session_key":
					del request.session[key]

			if user:
				current_user = Profile.objects.filter(user__id=request.user.id)
				current_user.update(old_cart="")


			return redirect(payment_url)

			#messages.success(request, "Order Placed!")
			#return redirect('home')			

		else:
			# not logged in
			# Create Order
			create_order = Order(full_name=full_name, email=email, shipping_address=shipping_address, amount_paid=amount_paid)
			create_order.save()

			# Add order items
			
			# Get the order ID
			order_id = create_order.pk
			
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
            	'return_url': 'https://greenmarvelstore-production.up.railway.app/home/',  
            	'cancel_url': 'https://greenmarvelstore-production.up.railway.app/payment/payment_cancel/',
            	'notify_url': 'https://greenmarvelstore-production.up.railway.app/payment/payment_notify/',

            	'name_first': payment.name_first,  # Assuming first name is the first part of full_name
            	'name_last':  payment.name_last,   # Assuming last name is the last part of full_name
            	'email_address': payment.email,
            	'cell_number': payment.phone,

            	'm_payment_id': payment.order_id,
            	'amount': payment.amount,
            	'item_name': 'Order Product',
            	}
			signature = generate_signature(data, settings.PAYFAST_PASSPHRASE)
			data['signature'] = signature

			payfast_url = "https://sandbox.payfast.co.za/eng/process?"
			#payment_url = payfast_url + urllib.parse.urlencode(data).replace('%2B', '+')
			payment_url = payfast_url + urllib.parse.urlencode(data)

			# Clear the cart
			for key in list(request.session.keys()):
				if key == "session_key":
					del request.session[key]

			#if user:
			#	current_user = Profile.objects.filter(user__id=request.user.id)
			#	current_user.update(old_cart="")

			#messages.success(request, "Order Placed!")		
			#return redirect('home')

			return redirect(payment_url)
			
			
    

	#else:
	#	messages.success(request, "Access Denied")
	#	return redirect('home')


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




def billing_info(request):
	if request.POST:
		# Get the cart
		cart = Cart(request)
		cart_products = cart.get_prods
		quantities = cart.get_quants
		totals = cart.cart_total()

		# Create a session with Shipping Info
		my_shipping = request.POST
		request.session['my_shipping'] = my_shipping

		# Check to see if user is logged in
		if request.user.is_authenticated:
			# Get The Billing Form
			billing_form = PaymentForm()
			return render(request, "payment/billing_info.html", {"cart_products":cart_products, "quantities":quantities, "totals":totals, "shipping_info":request.POST, "billing_form":billing_form})

		else:
			# Not logged in
			# Get The Billing Form
			billing_form = PaymentForm()
			return render(request, "payment/billing_info.html", {"cart_products":cart_products, "quantities":quantities, "totals":totals, "shipping_info":request.POST, "billing_form":billing_form})
		
		shipping_form = request.POST
		return render(request, "payment/billing_info.html", {"cart_products":cart_products, "quantities":quantities, "totals":totals, "shipping_form":shipping_form})	
	else:
		messages.success(request, "Access Denied")
		return redirect('landing')



def checkout(request):
	# Get the cart
	cart = Cart(request)
	cart_products = cart.get_prods
	quantities = cart.get_quants
	totals = cart.cart_total()

	if request.user.is_authenticated:
		# Checkout as logged in user
		# Shipping User
		shipping_user = ShippingAddress.objects.get(user__id=request.user.id)
		# Shipping Form
		shipping_form = ShippingForm(request.POST or None, instance=shipping_user)
		return render(request, "payment/checkout.html", {"cart_products":cart_products, "quantities":quantities, "totals":totals, "shipping_form":shipping_form, 'shipping_user': shipping_user })
	else:
		# Checkout as guest
		shipping_form = ShippingForm(request.POST or None)
		return render(request, "payment/checkout.html", {"cart_products":cart_products, "quantities":quantities, "totals":totals, "shipping_form":shipping_form})



def payment_success(request):
	return render(request, "payment/payment_success.html", {})

def payment_success(request):
    return render(request, 'payments/payment_success.html')

def payment_cancel(request):
    return render(request, 'payment/payment_cancel.html')










