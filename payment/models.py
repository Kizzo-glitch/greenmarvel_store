from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, pre_save
from greenmarv.models import Product
from django.dispatch import receiver 
import datetime
from decimal import Decimal



SA_PROVINCE_CHOICES = [
	('Gauteng',        'Gauteng'),
	('Western Cape',   'Western Cape'),
	('KwaZulu-Natal',  'KwaZulu-Natal'),
	('Eastern Cape',   'Eastern Cape'),
	('Free State',     'Free State'),
	('Limpopo',        'Limpopo'),
	('Mpumalanga',     'Mpumalanga'),
	('North West',     'North West'),
	('Northern Cape',  'Northern Cape'),
] 


class ShippingAddress(models.Model):
	user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
	shipping_full_name = models.CharField(max_length=255, null=True, blank=True)
	shipping_email = models.CharField(max_length=255, null=True, blank=True)
	shipping_phone = models.CharField(max_length=20, null=True, blank=True)
	shipping_address1 = models.CharField(max_length=255, null=True, blank=True)
	shipping_apartment = models.CharField(max_length=255, null=True, blank=True)
	shipping_city = models.CharField(max_length=255, null=True, blank=True)
	shipping_province = models.CharField(max_length=20, choices=SA_PROVINCE_CHOICES, null=True, blank=True,
		help_text="South African province for delivery")
	shipping_zipcode = models.CharField(max_length=255, null=True, blank=True)
	shipping_country = models.CharField(max_length=255, null=True, blank=True, default='South Africa')


	# Don't pluralize address
	class Meta:
		verbose_name_plural = "Shipping Address"


	def __str__(self):
		return f'Shipping Address - {str(self.id)}'


# Create a user Shipping Address by default when user signs up
def create_shipping(sender, instance, created, **kwargs):
	if created:
		user_shipping = ShippingAddress(user=instance)
		user_shipping.save()

# Automate the profile thing
post_save.connect(create_shipping, sender=User)



# Create Order Model
class Order(models.Model):

	STATUS_CHOICES = [
		('pending_payment', 'Pending Payment'),
		('paid',            'Paid'),
		('dispatched',      'Dispatched'),       
		('in_transit',      'In Transit'),       
		('delivered',       'Delivered'),        # NEW
		('collected',       'Collected'),        # NEW (for pickup orders)
		('cancelled',       'Cancelled'),
		('failed',          'Failed'),
	]
	
	user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
	full_name = models.CharField(max_length=250)
	email = models.EmailField(max_length=250)
	shipping_address = models.TextField(max_length=15000)
	amount_paid = models.DecimalField(max_digits=7, decimal_places=2)
	total_weight = models.DecimalField(default=0, max_digits=7, decimal_places=2)
	session_key = models.CharField(max_length=100, null=True, blank=True)
	
	date_ordered = models.DateTimeField(auto_now_add=True)
	date_paid = models.DateTimeField(null=True, blank=True)	
	date_shipped = models.DateTimeField(blank=True, null=True)
	shipped = models.BooleanField(default=False)

	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_payment')
	pickup_point_code = models.CharField(max_length=50, blank=True, null=True)
	phone = models.CharField(max_length=20, blank=True)  
	  
	# ============================================
	# Date timestamps for each stage
	# ============================================
	date_dispatched = models.DateTimeField(null=True, blank=True)
	date_in_transit = models.DateTimeField(null=True, blank=True)
	date_delivered  = models.DateTimeField(null=True, blank=True)
	date_collected  = models.DateTimeField(null=True, blank=True)

	# ============================================
	# Shipping service fields -- For ADMIN VIEW ONLY (not shown to customer)
	# ============================================
	shipping_service_code = models.CharField(
		max_length=20,
		blank=True,
		default='',
		choices=[
			('economy',  'Economy Delivery (5-7 days)'),
			('standard', 'Standard Delivery (3-5 days)'),
			('express',  'Express Delivery (2-3 days)'),
		],
		help_text="Shipping tier the customer selected at checkout"
	)
	
	shipping_service_name = models.CharField(max_length=100, blank=True, default='',
		help_text="Human-readable shipping service name"
	)
	
	shipping_cost = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'),
		help_text="Amount charged to customer for shipping"
	)
	
	shipping_actual_cost = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'),
		help_text="What we actually pay the courier (internal — never shown to customer)"
	)
	
	courier_booked = models.CharField(max_length=50, blank=True, default='',
		help_text="Which courier you actually booked via Bob Go (e.g., 'Courier Guy', 'MTE'). Update after booking."
	)
	
	tracking_number = models.CharField(max_length=100, blank=True, default='',
		help_text="Tracking number from the courier after booking via Bob Go"
	)

	# ============================================
	# OPTIONAL helper property
	# ============================================
	@property
	def shipping_margin(self):
		"""Profit on shipping (what we charged - what we paid courier)."""
		return self.shipping_cost - self.shipping_actual_cost
	

	# ============================================
	# Helper methods for the track template
	# ============================================
	
	def get_progress_step(self):
		"""
		Returns current step number (1–4) for the progress bar.
		Used by the track_order template.
		
		Collection orders have a different progression than courier orders.
		"""
		is_collection = self.shipping_service_code == 'collection'
		
		if is_collection:
			# Pickup flow: Placed → Paid → Ready → Collected
			if self.status == 'collected':
				return 4
			elif self.status in ('dispatched', 'in_transit'):
				return 3  # "ready for pickup"
			elif self.status == 'paid':
				return 2
			else:
				return 1
		else:
			# Courier flow: Placed → Dispatched → In Transit → Delivered
			if self.status == 'delivered':
				return 4
			elif self.status == 'in_transit':
				return 3
			elif self.status == 'dispatched':
				return 2
			elif self.status == 'paid':
				return 1
			else:
				return 1
	
	def get_progress_labels(self):
		"""Step labels for the customer-facing progress bar."""
		if self.shipping_service_code == 'collection':
			return [
				('Order placed',     'order placed'),
				('Payment confirmed', 'payment confirmed'),
				('Ready for pickup',  'ready for pickup'),
				('Collected',         'collected'),
			]
		else:
			return [
				('Order placed', 'order placed'),
				('Dispatched',   'dispatched'),
				('In transit',   'in transit'),
				('Delivered',    'delivered'),
			]
	
	def get_next_valid_statuses(self):
		"""
		Returns list of valid next statuses from the current state.
		Used by the admin to show only sensible "advance" options.
		"""
		is_collection = self.shipping_service_code == 'collection'
		
		transitions = {
			'pending_payment': ['paid', 'cancelled', 'failed'],
			'paid':            ['dispatched', 'cancelled'],
			'dispatched':      ['in_transit', 'collected'] if is_collection else ['in_transit'],
			'in_transit':      ['delivered', 'collected'] if is_collection else ['delivered'],
			'delivered':       ['delivered'],  # terminal
			'collected':       ['collected'],  # terminal
			'cancelled':       ['cancelled'],  # terminal
			'failed':          ['failed'],     # terminal
		}
		return transitions.get(self.status, [])
	
	def get_next_status_suggestion(self):
		"""The most likely next step (for the "Advance" button)."""
		is_collection = self.shipping_service_code == 'collection'
		
		progression = {
			'pending_payment': 'paid',
			'paid':            'dispatched',
			'dispatched':      'collected' if is_collection else 'in_transit',
			'in_transit':      'collected' if is_collection else 'delivered',
		}
		return progression.get(self.status)
	
	
	def __str__(self):
		return f'Order - {str(self.id)}'

# Auto Add shipping Date
@receiver(pre_save, sender=Order)
def set_shipped_date_on_update(sender, instance, **kwargs):
	if instance.pk:
		now = datetime.datetime.now()
		obj = sender._default_manager.get(pk=instance.pk)
		if instance.shipped and not obj.shipped:
			instance.date_shipped = now

class OrderItem(models.Model):
	# Foreign Keys
	order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True)
	product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True)
	user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

	quantity = models.PositiveBigIntegerField(default=1)
	price = models.DecimalField(max_digits=7, decimal_places=2)


	def __str__(self):
		return f'Order Item - {str(self.id)}'


# ====================================================================================
# To be deleted - we will just use the fields on the Order model instead of a separate CourierGuy model, 
# since we only have one courier and it simplifies things. 
# Keeping this here for reference in case we want to add more couriers in the future.
# ====================================================================================
class CourierGuy(models.Model):
	order = models.OneToOneField(Order, on_delete=models.CASCADE)
	tracking_number = models.CharField(max_length=100, blank=True, null=True)
	courier_service = models.CharField(max_length=100, default="Courier Guy")
	shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
	estimated_delivery = models.DateField(null=True, blank=True)
	status = models.CharField(max_length=50, default="Pending")

	def __str__(self):
		return f"Shipping Info - {self.order.id}"

class PayfastPayment(models.Model):
	pf_payment_id = models.CharField(max_length=100, blank=True)
	order_id = models.CharField(max_length=100, null=True)
	name_first = models.CharField(max_length=100)
	name_last = models.CharField(max_length=100)
	amount = models.DecimalField(max_digits=10, decimal_places=2)
	email = models.EmailField(max_length=250)
	status = models.CharField(max_length=20, default='Pending')
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	itn_payload = models.TextField(null=True, blank=True)
	phone = models.CharField(max_length=100, blank=True, null=True,)

	def __str__(self):
		return f'PayfastPayment - {self.order_id}'


class TrackingEvent(models.Model):
	order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name="tracking_events")
	status = models.CharField(max_length=255, blank=True, null=True)  # e.g., "Collected", "In Transit"
	description = models.TextField(blank=True, null=True)
	timestamp = models.DateTimeField()

	def __str__(self):
		return f"{self.status} at {self.timestamp}"










