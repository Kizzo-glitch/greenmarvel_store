from django.db import models
#from django.contrib.auth.models import AbstractUser
import datetime
from django.contrib.auth.models import User
from django.db.models.signals import post_save



# Create Customer Profile
class Profile(models.Model):
	user = models.OneToOneField(User, on_delete=models.CASCADE)
	date_modified = models.DateTimeField(User, auto_now=True)
	phone = models.CharField(max_length=20, blank=True)
	address1 = models.CharField(max_length=200, blank=True)
	apartment = models.CharField(max_length=200, blank=True)
	city = models.CharField(max_length=200, blank=True)
	province = models.CharField(max_length=200, blank=True)
	zipcode = models.CharField(max_length=200, blank=True)
	country = models.CharField(max_length=200, blank=True)
	old_cart = models.CharField(max_length=200, blank=True, null=True)

	def __str__(self):
		return self.user.username

# Create a user Profile by default when user signs up
def create_profile(sender, instance, created, **kwargs):
	if created:
		user_profile = Profile(user=instance)
		user_profile.save()

# Automate the profile thing
post_save.connect(create_profile, sender=User)



# Categories of products
class Category(models.Model):
	name = models.CharField(max_length=50)
	
	def __str__(self):
		return self.name


	class Meta:
		verbose_name_plural = 'Categories'


#class CustomUser(AbstractUser):
#	email = models.EmailField(unique=True)


class Customer(models.Model):
	first_name = models.CharField(max_length=50)
	last_name = models.CharField(max_length=50)
	phone = models.CharField(max_length=20)
	email = models.EmailField(max_length=100)
	password = models.CharField(max_length=50)

	def __str__(self):
		return f'{self.first_name} {self.last_name}'



class Product(models.Model):
	name = models.CharField(max_length=50)
	price = models.DecimalField(default=0, decimal_places=2, max_digits=5)
	Category = models.ForeignKey(Category, on_delete=models.CASCADE, default=1)
	description = models.CharField(max_length=500, default='', blank=True, null=True)
	image = models.ImageField(upload_to='uploads/product/')
	weight = models.DecimalField(default=0, max_digits=5, decimal_places=2)  # Weight in grams
	sale = models.BooleanField(default=False)
	sale_price = models.DecimalField(default=0, decimal_places=2, max_digits=5)




class Order(models.Model):
	product = models.ForeignKey(Product, on_delete=models.CASCADE)
	customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
	quantity = models.IntegerField(default=1)
	address = models.CharField(max_length=500, default='', blank=True)
	phone = models.CharField(max_length=20, default='', blank=True)
	date = models.DateField(default=datetime.datetime.today)
	status = models.BooleanField(default=False)


	def __str__(self):
		return self.product



class Influencer(models.Model):
	name = models.CharField(max_length=50)
	email = models.EmailField(max_length=250)
	commission_rate = models.DecimalField(default=0, decimal_places=2, max_digits=5)  # Percentage rate of commission

	def __str__(self):
		return self.name

class DiscountCode(models.Model):
	code = models.CharField(max_length=20, unique=True)
	influencer = models.ForeignKey(Influencer, on_delete=models.CASCADE, related_name='discount_codes')
	discount_percentage = models.IntegerField(default=0)  # Discount percentage
	usage_count = models.DecimalField(default=0, decimal_places=2, max_digits=5)
	total_before_discount = models.DecimalField(null=True, blank=True, decimal_places=2, max_digits=5)
	is_active = models.BooleanField(default=False)

	def __str__(self):
		return f'{self.code} ({self.discount_percentage}% discount by {self.influencer.name})'

