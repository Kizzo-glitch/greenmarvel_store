from greenmarv.models import Product, Profile
from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ObjectDoesNotExist
from greenmarv.models import DiscountCode, Influencer

class Cart():
	def __init__(self, request):
		self.session = request.session

		# Get request
		self.request = request

		#Get current session key if it exists
		cart = self.session.get('session_key')

		# If the user is new, no session key! Create one
		if 'session_key' not in request.session:
			cart = self.session['session_key'] = {}


		# Make sure cart is available on all pages of site
		self.cart = cart



	def db_add(self, product, quantity):
		product_id = str(product)
		product_qty = str(quantity)
		# Logic
		if product_id in self.cart:
			pass
		else:
			#self.cart[product_id] = {'price': str(product.price)}
			self.cart[product_id] = int(product_qty)

		self.session.modified = True

		# Deal with logged in user
		if self.request.user.is_authenticated:
			# Get the current user profile
			current_user = Profile.objects.filter(user__id=self.request.user.id)
			# Convert {'3':1, '2':4} to {"3":1, "2":4}
			carty = str(self.cart)
			carty = carty.replace("\'", "\"")
			# Save carty to the Profile Model
			current_user.update(old_cart=str(carty))



	def add(self, product, quantity):
		product_id = str(product.id)
		product_qty = str(quantity)

		#logic
		if product_id in self.cart:
			pass

		else:
			#self.cart[product_id] = {'price': str(product.price)}
			self.cart[product_id] = int(product_qty)


		self.session.modified = True

		# Deal with logged in user
		if self.request.user.is_authenticated:
			# Get the current user profile
			current_user = Profile.objects.filter(user__id=self.request.user.id)
			# Convert {'3':1, '2':4} to {"3":1, "2":4}
			carty = str(self.cart)
			carty = carty.replace("\'", "\"")
			# Save carty to the Profile Model
			current_user.update(old_cart=str(carty))


	def cart_total(self, discount_code=None):
        # Get product IDs
		product_ids = self.cart.keys()
        # Lookup those keys in the product database
		products = Product.objects.filter(id__in=product_ids)
        # Get quantities
		quantities = self.cart
        # Start counting at 0
		total = Decimal(0)
		#total = 0

        # Calculate the total price
		for key, value in quantities.items():
            # Convert key string into int so we can do math
			key = int(key)
			for product in products:
				if product.id == key:
					if product.sale:
						total += product.sale_price * value
					else:
						total += product.price * value

        # Apply discount if a valid discount code exists
		discount_amount = Decimal(0)
		
		if discount_code:
			try:
				discount = DiscountCode.objects.get(code=discount_code, is_active=True)
                # Apply percentage-based discount
				discount_amount = Decimal(discount.discount_percentage) / 100 * total
			except ObjectDoesNotExist:
				pass  # Ignore if discount code is invalid
        
        # Total after discount
		total_after_discount = total - discount_amount

		return total_after_discount if discount_amount > 0 else total


	def __len__(self):
		return len(self.cart)



	def get_prods(self):
		# Get ids from cart
		product_ids = self.cart.keys()
		# Use ids to lookup products in database model
		products = Product.objects.filter(id__in=product_ids)

		# Return those looked up products
		return products


	def get_quants(self):
		quantities = self.cart
		return quantities


	def update(self, product, quantity):
		product_id = str(product)
		product_qty = int(quantity)

		# Get cart
		ourcart = self.cart
		# Update Dictionary/cart
		ourcart[product_id] = product_qty

		self.session.modified = True

		# Deal with logged in user
		if self.request.user.is_authenticated:
			# Get the current user profile
			current_user = Profile.objects.filter(user__id=self.request.user.id)
			# Convert {'3':1, '2':4} to {"3":1, "2":4}
			carty = str(self.cart)
			carty = carty.replace("\'", "\"")
			# Save carty to the Profile Model
			current_user.update(old_cart=str(carty))

		thing = self.cart
		return thing



	def delete(self, product):
		product_id = str(product)
		# Delete from dictionary/cart
		if product_id in self.cart:
			del self.cart[product_id]

		self.session.modified = True

		# Deal with logged in user
		if self.request.user.is_authenticated:
			# Get the current user profile
			current_user = Profile.objects.filter(user__id=self.request.user.id)
			# Convert {'3':1, '2':4} to {"3":1, "2":4}
			carty = str(self.cart)
			carty = carty.replace("\'", "\"")
			# Save carty to the Profile Model
			current_user.update(old_cart=str(carty))
