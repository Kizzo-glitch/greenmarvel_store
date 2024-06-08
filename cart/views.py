from django.shortcuts import render, get_object_or_404
from .cart import Cart
from greenmarv.models import Product
from django.http import JsonResponse
from django.contrib import messages


# Create your views here.
def cart_summary(request):
	# Get the cart
	cart = Cart(request)
	cart_products = cart.get_prods
	quantities = cart.get_quants
	totals = cart.cart_total()
	return render(request, "cart_summary.html", {"cart_products":cart_products, "quantities":quantities, "totals":totals})



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
		messages.success(request, ("Item Added to Cart..."))
		response = JsonResponse({'qty': cart_quantity})
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