from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, pre_save
from greenmarv.models import Product
from django.dispatch import receiver 
import datetime



# Create your models here.

class ShippingAddress(models.Model):
	user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
	shipping_full_name = models.CharField(max_length=255, null=True, blank=True)
	shipping_email = models.CharField(max_length=255, null=True, blank=True)
	shipping_phone = models.CharField(max_length=20, null=True, blank=True)
	shipping_address1 = models.CharField(max_length=255, null=True, blank=True)
	shipping_apartment = models.CharField(max_length=255, null=True, blank=True)
	shipping_city = models.CharField(max_length=255, null=True, blank=True)
	shipping_province = models.CharField(max_length=255, null=True, blank=True)
	shipping_zipcode = models.CharField(max_length=255, null=True, blank=True)
	shipping_country = models.CharField(max_length=255, null=True, blank=True)


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
	# Foreign Key
	user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
	full_name = models.CharField(max_length=250)
	email = models.EmailField(max_length=250)
	shipping_address = models.TextField(max_length=15000)
	amount_paid = models.DecimalField(max_digits=7, decimal_places=2)
	date_ordered = models.DateTimeField(auto_now_add=True)	
	shipped = models.BooleanField(default=False)
	date_shipped = models.DateTimeField(blank=True, null=True)
	total_weight = models.DecimalField(default=0, max_digits=7, decimal_places=2)
	
	
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
	

# Create Order Items Model
class OrderItem(models.Model):
	# Foreign Keys
	order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True)
	product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True)
	user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

	quantity = models.PositiveBigIntegerField(default=1)
	price = models.DecimalField(max_digits=7, decimal_places=2)


	def __str__(self):
		return f'Order Item - {str(self.id)}'



