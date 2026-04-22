from greenmarv.models import Product, Profile
from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ObjectDoesNotExist
from greenmarv.models import DiscountCode, Influencer
import json




class Cart():
    def __init__(self, request):
        self.session = request.session
        self.request = request

        # Get current session cart if it exists
        cart = self.session.get('session_key')

        # If new user, create empty cart
        if 'session_key' not in request.session:
            cart = self.session['session_key'] = {}

        self.cart = cart

    def _save_to_profile(self):
        """Sync cart to user profile if logged in."""
        if self.request.user.is_authenticated:
            current_user = Profile.objects.filter(user__id=self.request.user.id)
            # Use json.dumps — proper JSON formatting, no fragile string replace
            current_user.update(old_cart=json.dumps(self.cart))

    def add(self, product, quantity=1):
        """Add a product to the cart. If already there, INCREMENT the quantity."""
        product_id = str(product.id)
        quantity = int(quantity)

        if product_id in self.cart:
            # Increment existing quantity
            self.cart[product_id] = int(self.cart[product_id]) + quantity
        else:
            self.cart[product_id] = quantity

        self.session.modified = True
        self._save_to_profile()

    def db_add(self, product, quantity):
        """Used when restoring a cart from the database on login."""
        product_id = str(product)
        quantity = int(quantity)

        if product_id not in self.cart:
            self.cart[product_id] = quantity

        self.session.modified = True
        self._save_to_profile()

    def update(self, product, quantity):
        """Set quantity directly (used by the quantity selector in cart page)."""
        product_id = str(product)
        quantity = int(quantity)

        if quantity <= 0:
            self.delete(product_id)
            return

        self.cart[product_id] = quantity
        self.session.modified = True
        self._save_to_profile()

    def delete(self, product):
        """Remove a product from the cart."""
        product_id = str(product)
        if product_id in self.cart:
            del self.cart[product_id]

        self.session.modified = True
        self._save_to_profile()

    def __len__(self):
        """Total number of items (summed quantities) in cart."""
        return sum(int(qty) for qty in self.cart.values())

    def get_prods(self):
        """Get Product objects currently in the cart."""
        product_ids = self.cart.keys()
        return Product.objects.filter(id__in=product_ids)

    def get_quants(self):
        """Return the raw {product_id: quantity} dict."""
        return self.cart

    def cart_total(self):
        """Sum up the total cost of the cart, respecting sale prices."""
        product_ids = self.cart.keys()
        products = Product.objects.filter(id__in=product_ids)
        quantities = self.cart
        total = Decimal('0.00')

        for product in products:
            pid = str(product.id)
            if pid in quantities:
                qty = int(quantities[pid])
                price = product.sale_price if product.is_sale else product.price
                total += Decimal(price) * qty

        return total

    def heritage_total(self):
        """Heritage Day promo: cheapest item free when buying 3+ items."""
        product_ids = self.cart.keys()
        products = Product.objects.filter(id__in=product_ids)
        quantities = self.cart

        # Build list of unit prices (one entry per item, respecting quantities)
        all_prices = []
        for product in products:
            pid = str(product.id)
            if pid in quantities:
                qty = int(quantities[pid])
                price = product.sale_price if product.is_sale else product.price
                all_prices.extend([Decimal(price)] * qty)

        # Need at least 3 items to qualify
        if len(all_prices) < 3:
            return self.cart_total()

        # Subtract the cheapest item
        all_prices.sort()
        return sum(all_prices) - all_prices[0]

    def cart_weight(self):
        """Total weight for shipping calculations."""
        product_ids = self.cart.keys()
        products = Product.objects.filter(id__in=product_ids)
        total_weight = Decimal('0.00')

        for product in products:
            pid = str(product.id)
            if pid in self.cart:
                qty = int(self.cart[pid])
                total_weight += Decimal(product.weight) * qty

        return total_weight


class Cart2():
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


	def cart_weight(self):
		product_ids = self.cart.keys()
		products = Product.objects.filter(id__in=product_ids)
		quantities = self.cart
		total_weight = 0

		for key, value in quantities.items():
			key = int(key)
			for product in products:
				if product.id == key:
					total_weight += product.weight * value

		return total_weight



	def cart_total2(self, discount_code=None, heritage_promo=False):
		product_ids = self.cart.keys()
		products = Product.objects.filter(id__in=product_ids)
		quantities = self.cart
		total = Decimal(0)
		all_prices = []

		for key, value in quantities.items():
			key = int(key)
			for product in products:
				if product.id == key:
					price = product.sale_price if product.sale else product.price
					total += price * value
					# add each item individually for promo logic
					all_prices.extend([price] * value)

		# Percentage discount
		discount_amount = Decimal(0)
		if discount_code:
			try:
				discount = DiscountCode.objects.get(code=discount_code, is_active=True)
				discount_amount = Decimal(discount.discount_percentage) / 100 * total
			except ObjectDoesNotExist:
				pass

		# Heritage Day: Buy 3 get cheapest free
		heritage_discount = Decimal(0)
		if heritage_promo and len(all_prices) >= 3:
			cheapest = min(all_prices)
			heritage_discount = cheapest  # subtract cheapest item

		total_after_discount = total - discount_amount - heritage_discount
		return max(total_after_discount, Decimal(0))



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


	def heritage_total(self):
		product_ids = self.cart.keys()
		products = Product.objects.filter(id__in=product_ids)
		quantities = self.cart
		total = Decimal(0)
		all_prices = []

		for key, value in quantities.items():
			key = int(key)
			for product in products:
				if product.id == key:
					price = product.sale_price if product.sale else product.price
					total += price * value
					all_prices.extend([price] * value)

		if len(all_prices) >= 3:
			total -= min(all_prices)

		return total





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
