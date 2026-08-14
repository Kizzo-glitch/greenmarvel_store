from django.db import models
#from django.contrib.auth.models import AbstractUser
import datetime
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.utils.text import slugify
from django.urls import reverse
from django.db import models
from django.core.validators import EmailValidator
 


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
	country = models.CharField(max_length=200, blank=True, default='South Africa')
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
	subtitle = models.CharField(max_length=100, default='', blank=True)
	price = models.DecimalField(default=0, decimal_places=2, max_digits=7) 
	category = models.ForeignKey('Category', on_delete=models.CASCADE, default=1) 
	# Content sections
	description = models.TextField(max_length=500, default='', blank=True, null=True)
	ingredients = models.TextField(max_length=1000, default='', blank=True, null=True)
	benefits = models.TextField(max_length=2000, default='', blank=True, null=True)
	use = models.TextField(max_length=2000, default='', blank=True, null=True)
	
	# Visuals
	image = models.ImageField(upload_to='uploads/product/')
	
	# Brand/UI specific fields
	badge_text = models.CharField(max_length=100, default='100% Organic', help_text="e.g., 100% Organic or Best Seller")
	tag_1 = models.CharField(max_length=50, blank=True, help_text="e.g., ⚡ Fast Acting")
	tag_2 = models.CharField(max_length=50, blank=True, help_text="e.g., 💧 Daily Use")
	tag_3 = models.CharField(max_length=50, blank=True, help_text="e.g., 🌿 100ml")
	
	# Specs & Sale
	weight = models.DecimalField(default=0, max_digits=5, decimal_places=2)
	is_sale = models.BooleanField(default=False)
	sale_price = models.DecimalField(default=0, decimal_places=2, max_digits=7)
	
	slug = models.SlugField(
		max_length=200,
		unique=True,
		blank=True,
		default='',
		help_text="URL-friendly version of name — auto-generated if left blank"
	)
	
	def save(self, *args, **kwargs):
		# Auto-generate slug from name if not manually set
		if not self.slug:
			base_slug = slugify(self.name)
			slug = base_slug
			counter = 1
			# Handle duplicates by appending -2, -3, etc.
			while Product.objects.filter(slug=slug).exclude(id=self.id).exists():
				slug = f"{base_slug}-{counter}"
				counter += 1
			self.slug = slug
		super().save(*args, **kwargs)
	
	def get_absolute_url(self):
		"""Canonical URL for this product. Used in sitemaps and share links."""
		return reverse('product_detail', kwargs={'slug': self.slug})

	def __str__(self):
		return self.name

	@property
	def current_price(self):
		if self.is_sale:
			return self.sale_price
		return self.price



class Influencer(models.Model):
	name = models.CharField(blank=True, max_length=50)
	phone = models.CharField(blank=True, max_length=50)
	email = models.EmailField(blank=True, max_length=250)
	commission_rate = models.DecimalField(default=0, decimal_places=2, max_digits=5)  # Percentage rate of commission

	def __str__(self):
		return self.name

 
class DiscountCode(models.Model):
    code = models.CharField(max_length=20, unique=True)
    influencer = models.ForeignKey(
        Influencer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='discount_codes',
    )
    discount_percentage = models.IntegerField(
        default=0,
        help_text="Percentage off. Use this OR amount_off, not both.",
    )
    amount_off = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Fixed Rand amount off. Use this OR discount_percentage.",
    )
    usage_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times this code has been used.",
    )
    total_before_discount = models.DecimalField(
        max_digits=10,               
        decimal_places=2,
        null=True,
        blank=True,
        default=0,
        help_text="Cumulative Rand value of orders that used this code.",
    )
    is_active = models.BooleanField(default=False)
 
    # Optional but useful — track when the code was created
    date_created = models.DateTimeField(auto_now_add=True, null=True)
 
    def __str__(self):
        if self.influencer:
            return f'{self.code} ({self.discount_percentage}% via {self.influencer.name})'
        return f'{self.code} ({self.discount_percentage}%)'
"""
class DiscountCode(models.Model):
	code = models.CharField(max_length=20, unique=True)
	influencer = models.ForeignKey(Influencer, on_delete=models.SET_NULL, null=True, blank=True, related_name='discount_codes')
	discount_percentage = models.IntegerField(default=0)  # Discount percentage
	amount_off = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
	usage_count = models.DecimalField(default=0, decimal_places=2, max_digits=5)
	total_before_discount = models.DecimalField(null=True, blank=True, decimal_places=2, max_digits=5)
	is_active = models.BooleanField(default=False)

	def __str__(self):
		return f'{self.code}' #({self.discount_percentage}% discount by {self.influencer.name})
"""
# ================================================================
# NEWSLETTER SUBSCRIPTION — Backend
# ================================================================
# Three files needed:
#   1. models.py         — Subscriber model
#   2. views.py          — subscribe endpoint
#   3. urls.py           — route it
#
# Save these in whichever Django app makes sense (probably 'store' or
# a new 'newsletter' app). Each section below shows where it goes.
# ================================================================
 
 
# ============================================================
# 1. MODEL — Add to your models.py
# ============================================================
 
class NewsletterSubscriber(models.Model):
    """
    Stores email addresses of customers who signed up for the newsletter.
    
    Simple by design — the point is to collect emails now, integrate
    with an ESP (Mailchimp/Brevo/etc) later when you're ready.
    """
    CHANNEL_CHOICES = [
        ('email', 'Email'),
        ('whatsapp', 'WhatsApp'),
    ]
 
    email = models.EmailField(
        unique=True,
        validators=[EmailValidator()],
        help_text="Subscriber's email address",
    )
    signup_channel = models.CharField(
        max_length=10,
        choices=CHANNEL_CHOICES,
        default='email',
        help_text="How they subscribed (for segmentation)",
    )
    date_subscribed = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Uncheck if user unsubscribes",
    )
    welcome_code_used = models.BooleanField(
        default=False,
        help_text="Set to True when they use their 10% off code",
    )
    source_page = models.CharField(
        max_length=100,
        blank=True,
        help_text="Which page they signed up from (home, checkout, etc)",
    )
 
    class Meta:
        ordering = ['-date_subscribed']
        verbose_name = 'Newsletter Subscriber'
        verbose_name_plural = 'Newsletter Subscribers'
 
    def __str__(self):
        return f"{self.email} ({self.date_subscribed:%Y-%m-%d})"