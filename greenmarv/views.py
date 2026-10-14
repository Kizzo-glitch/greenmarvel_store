from django.shortcuts import render, redirect, get_object_or_404

from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

from .models import (Product, Profile, DiscountCode, 
					 NewsletterSubscriber, Influencer, InfluencerClick)
from .forms import SignUpForm, UpdateUserForm, ChangePasswordForm, UserInfoForm
from django import forms

from django.db.models import Case, Value, When, BooleanField, Q
import json
from cart.cart import Cart

from payment.forms import ShippingForm
from payment.models import Order, ShippingAddress
from django.utils import timezone

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.core.validators import validate_email
from django.core.exceptions import ValidationError


from urllib.parse import urlparse
from datetime import timedelta
from django.http import Http404
from django.urls import reverse

from decimal import Decimal
from django.contrib.auth.decorators import login_required
from functools import wraps
from django.conf import settings


import hashlib
import logging
from .commission_calculations import _calculate_paid_commission, _calculate_pending_commission

from .tiktok_events_api import _send_event, build_user_data_from_request
 
logger = logging.getLogger(__name__)


# ================================================================
# CONSTANTS
# ================================================================
REFERRAL_WINDOW_DAYS = 30
SESSION_KEY_REFERRAL = 'referral'





# ============================================================
# REGISTER USER
# ============================================================
def register_user(request):
	if request.method == 'POST':
		form = SignUpForm(request.POST)
		
		if form.is_valid():
			form.save()
			username = form.cleaned_data['username']
			password = form.cleaned_data['password1']
			
			user = authenticate(username=username, password=password)
			login(request, user)
			
			# ============================================
			# NEW: Create ShippingAddress prefilled with
			# registration data so update_info has it ready
			# ============================================
			_ensure_shipping_address(user)
			
			messages.success(
				request,
				'Account created successfully — please complete your delivery details below.'
			)
			return redirect('update_info')
		else:
			messages.error(
				request,
				'Oops, there was a problem registering. Please correct the errors below.'
			)
			return render(request, 'register.html', {'form': form})
	else:
		form = SignUpForm()
		return render(request, 'register.html', {'form': form})


# ============================================================
# UPDATE INFO
# ============================================================
def update_info(request):
	# Auth guard
	if not request.user.is_authenticated:
		messages.error(request, "You must be logged in to access that page.")
		return redirect('home')
	
	# Use get_or_create instead of .get() — won't crash if missing
	current_user, _ = Profile.objects.get_or_create(user=request.user)
	
	# Ensure ShippingAddress exists and is prefilled with name/email
	# This handles two cases:
	#   (a) Existing users who registered before this code change
	#   (b) New users (already handled at registration but defensive)
	shipping_user = _ensure_shipping_address(request.user)
	
	form = UserInfoForm(request.POST or None, instance=current_user)
	shipping_form = ShippingForm(request.POST or None, instance=shipping_user)
	
	if request.method == 'POST':
		# FIXED: was 'or' — should be 'and' (both must be valid)
		if form.is_valid() and shipping_form.is_valid():
			form.save()
			shipping_form.save()
			messages.success(request, "Your info has been updated!")
			return redirect('shop')
		else:
			messages.error(request, "Please correct the errors below.")
	
	return render(request, "update_info.html", {
		'form': form,
		'shipping_form': shipping_form,
	})


# ============================================================
# HELPER — Used by both views
# ============================================================
def _ensure_shipping_address(user):
	"""
	Get or create the user's ShippingAddress, prefilling shipping_full_name
	and shipping_email from the User model if they're empty.
	
	Idempotent: safe to call on every visit. Only writes to DB when there's
	actually data to backfill.
	
	Returns the (refreshed) ShippingAddress instance.
	"""
	# Compose the full name from User.first_name + User.last_name
	full_name = f"{user.first_name} {user.last_name}".strip()
	
	shipping_user, created = ShippingAddress.objects.get_or_create(
		user=user,
		defaults={
			'shipping_full_name': full_name,
			'shipping_email': user.email or '',
		}
	)
	
	# If the ShippingAddress already existed but name/email are blank,
	# backfill from User (handles existing users from before this change)
	if not created:
		fields_to_update = []
		
		if not shipping_user.shipping_full_name and full_name:
			shipping_user.shipping_full_name = full_name
			fields_to_update.append('shipping_full_name')
		
		if not shipping_user.shipping_email and user.email:
			shipping_user.shipping_email = user.email
			fields_to_update.append('shipping_email')
		
		if fields_to_update:
			shipping_user.save(update_fields=fields_to_update)
	
	return shipping_user



def login_user(request):
	if request.method == "POST":
		username = request.POST['username']
		password = request.POST['password']
		user = authenticate(request, username=username, password=password)
		if user is not None:
			login(request, user)

			# Ensure the Profile exists for the user
			profile, created = Profile.objects.get_or_create(user=user)

			# Get their saved cart from database
			saved_cart = profile.old_cart
			# Convert database string to python dictionary
			if saved_cart:
				# Convert to dictionary using JSON
				converted_cart = json.loads(saved_cart)
				# Add the loaded cart dictionary to our session
				# Get the cart
				cart = Cart(request)
				# Loop thru the cart and add the items from the database
				for key,value in converted_cart.items():
					cart.db_add(product=key, quantity=value)
			
			next_url = request.GET.get('next') or request.POST.get('next')
			if next_url:
				return redirect(next_url)
			
			messages.success(request, ('You have been logged in'))
			return redirect('home')
		else:
			messages.success(request, ('There was an Error, please try again'))
			return redirect('login')

	else:
		return render(request, 'login.html', {})


def update_user(request):
	if request.user.is_authenticated:
		current_user = User.objects.get(id=request.user.id)
		user_form = UpdateUserForm(request.POST or None, instance=current_user)

		if user_form.is_valid():
			user_form.save()

			login(request, current_user)
			#messages.success(request, "User Has Been Updated!!")
			return redirect('home')
		return render(request, "update_user.html", {'user_form':user_form})
	else:
		messages.success(request, "You Must Be Logged In To Access That Page!!")
		return redirect('home')


def update_password(request):
	if request.user.is_authenticated:
		current_user = request.user
		# Did they fill out the form
		if request.method  == 'POST':
			form = ChangePasswordForm(current_user, request.POST)
			# Is the form valid
			if form.is_valid():
				form.save()
				messages.success(request, "Your Password Has Been Updated...")
				login(request, current_user)
				return redirect('update_user')
			else:
				for error in list(form.errors.values()):
					messages.error(request, error)
					return redirect('update_password')
		else:
			form = ChangePasswordForm(current_user)
			return render(request, "update_password.html", {'form':form})
	else:
		messages.success(request, "You Must Be Logged In To View That Page...")
		return redirect('home')


def home(request):
	#products = Product.objects.filter(name__icontains="combo")
	products = Product.objects.exclude(name__icontains="combo")

	#products = Product.objects.all()
	return render(request, 'home.html', {
		'products':products, 
		"now": timezone.now(),})

def product(request,pk):
	product = Product.objects.get(id=pk)
	return render(request, 'product.html', {'product':product})

def shop_all(request):
	# Annotate products: True (1) if it's a combo, False (0) if it's individual
	all_products = Product.objects.annotate(
		is_combo=Case(
			When(name__icontains="combo", then=Value(True)),
			default=Value(False),
			output_field=BooleanField(),
		)
	).order_by('is_combo', 'name') # Orders by False first (individuals), then True (combos)

	return render(request, 'shop.html', {'products': all_products})

def shop_all2(request):
	# Fetch all products, ordered by name or date added
	#all_products = Product.objects.all().order_by("-is_sale")
	all_products = Product.objects.all().order_by(name__icontains="-combo")
	return render(request, 'shop.html', {'products': all_products})


def product_detail(request, slug):
	"""
	Serve a single product page.
	URL: /product/<slug>/  e.g. /product/vitality-hair-spray/
	"""
	product = get_object_or_404(Product, slug=slug)
	
	# Fetch related products for the "You might also like" section
	related_products = Product.objects.exclude(id=product.id).order_by('?')[:3]
	
	return render(request, 'product_detail.html', {
		'product':          product,
		'related_products': related_products,
	})


def about(request):
	#products = Product.objects.all()
	return render(request, 'about.html', {})



def search(request):
	# Determine if they filled out the form
	if request.method == "POST":
		searched = request.POST['searched']
		# Query The Products DB Model
		searched = Product.objects.filter(Q(name__icontains=searched) | Q(description__icontains=searched))
		# Test for null
		if not searched:
			messages.success(request, "That Product Does Not Exist...Please try Again.")
			return render(request, "search.html", {})
		else:
			return render(request, "search.html", {'searched':searched})
	else:
		return render(request, "search.html", {})	
		
def logout_user(request):
	logout(request)
	#messages.success(request, ('You have been logged out'))
	return redirect('home')


WELCOME_CODE = 'WELCOME2026'
@require_POST
@csrf_protect
def newsletter_subscribe(request):
	email = request.POST.get('email', '').strip().lower()
 
	# Validation (unchanged)
	if not email:
		return JsonResponse({'success': False, 'message': 'Please enter your email address.'}, status=400)
	try:
		validate_email(email)
	except ValidationError:
		return JsonResponse({'success': False, 'message': 'Please enter a valid email address.'}, status=400)
 
	# ============================================
	# NEW: Fetch the welcome code dynamically
	# ============================================
	try:
		welcome_code = DiscountCode.objects.get(code='WELCOME2026', is_active=True).code
	except DiscountCode.DoesNotExist:
		# Fallback if the code was accidentally disabled or renamed
		# Log this because it means the welcome flow is broken
		print("⚠️  WELCOME2026 code not found or inactive — subscribers can't claim discount")
		welcome_code = None
 
	# Check if already subscribed (unchanged)
	existing = NewsletterSubscriber.objects.filter(email=email).first()
	if existing:
		if existing.is_active:
			return JsonResponse({
				'success': True,
				'code': welcome_code,
				'message': "You're already subscribed! Here's your code again.",
			})
		else:
			existing.is_active = True
			existing.save()
			return JsonResponse({
				'success': True,
				'code': welcome_code,
				'message': 'Welcome back! Your subscription has been reactivated.',
			})
 
	# Create new subscriber (unchanged)
	referer = request.META.get('HTTP_REFERER', '')
	source_page = referer.split('/')[-1] if referer else 'home'
 
	try:
		NewsletterSubscriber.objects.create(
			email=email,
			signup_channel='email',
			source_page=source_page[:100],
		)
	except Exception as e:
		print(f"Newsletter signup error for {email}: {e}")
		return JsonResponse({'success': False, 'message': 'Something went wrong. Please try again.'}, status=500)
 
	return JsonResponse({
		'success': True,
		'code': welcome_code,
		'message': "Welcome to the community!",
	})
 


# ================================================================
# tiktok_track view — the /tiktok/track/ endpoint
# ================================================================
# Called by tiktok_events.js from the browser after every client-side
# event fires. Forwards the event to TikTok Events API server-side
# with the same event_id so TikTok can dedupe.
#
# Add to whichever views.py makes sense (probably store or checkout).
# ================================================================

@csrf_protect
@require_POST
def tiktok_track(request):
	"""
	Generic client-side event forwarder.
	Called by tiktok_events.js after every browser-side event fires.
	"""
	try:
		payload = json.loads(request.body)
	except (ValueError, json.JSONDecodeError):
		return JsonResponse({'error': 'invalid JSON'}, status=400)

	event_name = payload.get('event')
	event_id = payload.get('event_id')
	event_data = payload.get('data', {})

	if not event_name or not event_id:
		return JsonResponse({'error': 'missing event or event_id'}, status=400)

	# Skip CompletePayment — the Payfast webhook handles it exclusively
	# to avoid double-firing with a different event_id format
	if event_name == 'CompletePayment':
		return JsonResponse({'ok': True, 'skipped': 'handled by webhook'})

	# Build user_data from the request (IP, UA, cookies, session)
	user_data = build_user_data_from_request(request)

	# Convert client-side payload into TikTok Events API properties format
	# tiktok_events.js sends: { contents: [...], value, currency, content_type }
	# TikTok Events API expects the same structure
	properties = {
		"contents":     event_data.get('contents', []),
		"value":        event_data.get('value', 0),
		"currency":     event_data.get('currency', 'ZAR'),
		"content_type": event_data.get('content_type', 'product'),
	}
	# Pass through order_id if present (unusual for browser events but safe)
	if 'order_id' in event_data:
		properties['order_id'] = event_data['order_id']

	_send_event(
		event_name=event_name,
		event_id=event_id,
		properties=properties,
		user_data=user_data,
	)

	return JsonResponse({'ok': True})



# ================================================================
# VIEW: /with/<slug>/
# ================================================================
def influencer_landing(request, slug, product_slug=None):
	"""
	Capture an influencer referral and redirect the visitor.
	
	URLs:
		/with/<slug>/                     → home
		/with/<slug>/<product_slug>/      → that product's detail page
	
	Side effects:
		- Logs an InfluencerClick row
		- Writes request.session['referral'] with attribution
		- Writes request.session['discount_code'] with the auto-apply code
		- Adds a messages.success() for the toast
	"""
	# ============================================
	# 1. Resolve influencer (404 if slug invalid)
	# ============================================
	try:
		influencer = Influencer.objects.get(slug=slug, is_active=True)
	except Influencer.DoesNotExist:
		logger.info(f"Influencer landing: unknown or inactive slug '{slug}'")
		raise Http404("This referral link isn't active.")
 
	# ============================================
	# 2. Resolve product (if deep link)
	# ============================================
	product = None
	if product_slug:
		try:
			product = Product.objects.get(slug=product_slug)
		except Product.DoesNotExist:
			logger.info(
				f"Influencer landing: valid influencer '{slug}' but unknown "
				f"product '{product_slug}' — redirecting to home instead"
			)
			# Soft fail: still attribute the referral, just land on home
			# rather than 404ing out of a legit influencer's link
 
	# ============================================
	# 3. Log the click (non-blocking)
	# ============================================
	try:
		# Ensure session key exists for anonymous visitors
		if not request.session.session_key:
			request.session.save()
 
		client_ip = _get_client_ip(request)
		referrer = _get_referrer_domain(request)
 
		InfluencerClick.objects.create(
			influencer=influencer,
			product_slug=product_slug or '',
			user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
			ip_hash=InfluencerClick.hash_ip(client_ip),
			session_key=request.session.session_key or '',
			referrer_domain=referrer,
		)
	except Exception as e:
		# Click logging must never block the redirect
		logger.error(f"Failed to log influencer click for '{slug}': {e}")
 
	# ============================================
	# 4. Save referral attribution to session
	# ============================================
	request.session[SESSION_KEY_REFERRAL] = {
		'influencer_id':   influencer.id,
		'influencer_slug': influencer.slug,
		'applied_at':      timezone.now().isoformat(),
	}
 
	# ============================================
	# 5. Auto-apply their active discount code (if any)
	# ============================================
	active_code = influencer.active_discount_code
	if active_code:
		request.session['discount_code'] = active_code.code
		
		# Pre-calculate the discount amount so cart_summary picks it up
		# NOTE: we don't set total_after_discount here because cart contents
		# might change between landing and checkout. cart_summary recalculates
		# on each visit using the code we just stored.
 
		_show_discount_toast(request, influencer, active_code)
	else:
		# No code attached — still show a warm welcome
		_show_referral_toast(request, influencer)
 
	# ============================================
	# 6. Redirect
	# ============================================
	if product:
		# Deep link → product detail
		# Adjust URL name to match your actual product_detail URL
		try:
			return redirect('product_detail', slug=product.slug)
		except Exception:
			# Fallback if URL name/kwargs differ in your project
			return redirect('home')
	else:
		return redirect('home')
 
 
# ================================================================
# HELPERS
# ================================================================
def _show_discount_toast(request, influencer, discount_code):
	"""Toast shown when influencer has a discount code to auto-apply."""
	# Format the discount for the message
	if discount_code.discount_percentage:
		discount_str = f"{discount_code.discount_percentage}%"
	elif discount_code.amount_off:
		discount_str = f"R{discount_code.amount_off:.0f}"
	else:
		discount_str = "a discount"
	
	messages.success(
		request,
		f"Welcome via {influencer.name}! ✨ {discount_str} off has been "
		f"applied to your cart — use code {discount_code.code} at checkout."
	)
 
 
def _show_referral_toast(request, influencer):
	"""Toast shown when influencer has no active discount code."""
	messages.success(
		request,
		f"Welcome via {influencer.name}! 🌿 Browse away — "
		f"your visit has been credited to them."
	)
 
 
def _get_client_ip(request):
	"""Extract real IP, respecting proxy headers (Railway puts customer IP in XFF)."""
	xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
	if xff:
		return xff.split(',')[0].strip()
	return request.META.get('REMOTE_ADDR', '')
 
 
def _get_referrer_domain(request):
	"""
	Extract just the hostname from the HTTP Referer header.
	Lets us answer "did this click come from TikTok, Instagram or direct?"
	without storing the full URL (which could leak private page paths).
	"""
	referer = request.META.get('HTTP_REFERER', '')
	if not referer:
		return ''
	try:
		parsed = urlparse(referer)
		return parsed.hostname[:200] if parsed.hostname else ''
	except Exception:
		return ''
 
 
# ================================================================
# UTILITY — used by cart_summary + process_order views in Phase 3
# ================================================================
def get_valid_referral(request):
	"""
	Return the active referral dict from session, or None if expired/missing.
	
	Call this from:
		- cart_summary (to show "attributed to X" in order summary)
		- process_order (to set Order.influencer when creating the record)
	
	Returns:
		dict with 'influencer_id', 'influencer_slug', 'applied_at'
		OR None if no referral or referral is older than 30 days.
	"""
	referral = request.session.get(SESSION_KEY_REFERRAL)
	if not referral:
		return None
 
	try:
		applied_at = timezone.datetime.fromisoformat(referral['applied_at'])
	except (ValueError, KeyError, TypeError):
		# Corrupted session data — clear it
		request.session.pop(SESSION_KEY_REFERRAL, None)
		return None
 
	# Check 30-day window
	expiry = applied_at + timedelta(days=REFERRAL_WINDOW_DAYS)
	if timezone.now() > expiry:
		# Expired — silently clear and return nothing
		request.session.pop(SESSION_KEY_REFERRAL, None)
		logger.info(
			f"Referral expired for session: slug='{referral.get('influencer_slug')}', "
			f"applied {(timezone.now() - applied_at).days} days ago"
		)
		return None
 
	return referral
 
 
def get_referred_influencer(request):
	"""
	Convenience: return the Influencer object this session was referred by, or None.
	Returns None if the influencer was deactivated between landing and checkout.
	"""
	referral = get_valid_referral(request)
	if not referral:
		return None
	try:
		return Influencer.objects.get(id=referral['influencer_id'], is_active=True)
	except Influencer.DoesNotExist:
		return None


# ================================================================
# DECORATOR — only logged-in influencers with a profile can access
# ================================================================
def influencer_required(view_func):
	"""
	Require: user is authenticated AND has an Influencer profile linked
	AND the Influencer is marked is_active.
	"""
	@wraps(view_func)
	@login_required(login_url='influencer_login')
	def wrapper(request, *args, **kwargs):
		try:
			influencer = request.user.influencer_profile
		except Influencer.DoesNotExist:
			messages.warning(
				request,
				"This area is for Marvelously Green influencers only."
			)
			return redirect('home')
 
		if not influencer.is_active:
			messages.warning(
				request,
				"Your influencer account is inactive. Please contact us."
			)
			return redirect('home')
 
		# Stash the influencer on the request for easy access in the view
		request.influencer = influencer
		return view_func(request, *args, **kwargs)
	return wrapper





# ================================================================
# DASHBOARD VIEW
# ================================================================
@influencer_required
def influencer_dashboard(request):
	"""
	Mobile-first dashboard showing clicks, orders, revenue, commission.
	
	Query params:
		?period=this_month | last_month | all_time   (default: this_month)
	"""
	influencer = request.influencer
	period = request.GET.get('period', 'this_month')
	
	# ============================================
	# Resolve date range from period
	# ============================================
	now = timezone.now()
	period_label = ''
	
	if period == 'last_month':
		# First day of last month → first day of this month
		first_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
		last_month_end = first_this - timedelta(seconds=1)
		start = last_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
		end = first_this
		period_label = start.strftime('%B %Y')
	elif period == 'all_time':
		start = None
		end = None
		period_label = 'All time'
	else:  # this_month (default)
		start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
		end = now
		period = 'this_month'
		period_label = now.strftime('%B %Y')
 
	# ============================================
	# Compute stats
	# ============================================
	stats = _calculate_stats(influencer, start, end)
 
	# ============================================
	# Recent attributed orders (always most-recent 10)
	# Not filtered by period — the table is a quick reference
	# ============================================
	PAID_STATUSES = ('paid', 'dispatched', 'in_transit', 'delivered', 'collected')
	recent_orders = (
		Order.objects
			 .filter(influencer=influencer, status__in=PAID_STATUSES)
			 .order_by('-date_paid')[:10]
	)
 
	# Enrich each order with per-order commission (for the table)
	recent_orders_enriched = []
	for order in recent_orders:
		subtotal = sum(
			item.price * item.quantity
			for item in order.orderitem_set.all()
		)
		commission = (
			subtotal * Decimal(str(influencer.commission_rate)) / Decimal('100')
		).quantize(Decimal('0.01'))
		
		recent_orders_enriched.append({
			'order':      order,
			'subtotal':   subtotal,
			'commission': commission,
			'item_count': order.orderitem_set.count(),
		})
 
	# ============================================
	# Build their sharable link
	# ============================================
	site_url = getattr(settings, 'SITE_URL', 'https://greenmarvel.co.za').rstrip('/')
	referral_url = f"{site_url}{influencer.referral_url_path}"

		# Add to the dashboard view, before context:
	pending_commission = _calculate_pending_commission(influencer)
	paid_commission = _calculate_paid_commission(influencer)
	
	# Find the most recent payout date
	last_payout = (
		Order.objects
			.filter(influencer=influencer, commission_paid_out_at__isnull=False)
			.order_by('-commission_paid_out_at')
			.values_list('commission_paid_out_at', flat=True)
			.first()
	)
	
	payout_summary = {
		'pending':      pending_commission,
		'paid':         paid_commission,
		'total':        pending_commission + paid_commission,
		'last_paid_at': last_payout,
	}
 
	# ============================================
	# Context
	# ============================================
	context = {
		'influencer':             influencer,
		'period':                 period,
		'period_label':           period_label,
		'stats':                  stats,
		'recent_orders':          recent_orders_enriched,
		'referral_url':           referral_url,
		'active_discount_code':   influencer.active_discount_code,
		'payout_summary': payout_summary,
	}
	return render(request, 'influencer/influencer_dashboard.html', context)
 
 
# ================================================================
# HELPER — compute all stats for one influencer in a date range
# ================================================================
def _calculate_stats(influencer, start, end):
	"""
	Returns a dict with:
		clicks, orders, products_sold, revenue, commission, aov, conversion_rate
	All numbers are for the given date range (None = all time).
	"""
	PAID_STATUSES = ('paid', 'dispatched', 'in_transit', 'delivered', 'collected')
	
	# Build querysets with optional date filtering
	clicks_qs = InfluencerClick.objects.filter(influencer=influencer)
	orders_qs = Order.objects.filter(influencer=influencer, status__in=PAID_STATUSES)
	
	if start and end:
		clicks_qs = clicks_qs.filter(clicked_at__gte=start, clicked_at__lt=end)
		orders_qs = orders_qs.filter(date_paid__gte=start, date_paid__lt=end)
 
	# Clicks
	clicks_count = clicks_qs.count()
 
	# Orders + revenue + products sold
	orders_count = orders_qs.count()
	
	revenue = Decimal('0.00')
	products_sold = 0
	for order in orders_qs.prefetch_related('orderitem_set'):
		for item in order.orderitem_set.all():
			revenue += item.price * item.quantity
			products_sold += item.quantity
 
	# Commission (based on product subtotal, not shipping)
	commission = (
		revenue * Decimal(str(influencer.commission_rate)) / Decimal('100')
	).quantize(Decimal('0.01'))
 
	# Average order value (based on product subtotal)
	if orders_count > 0:
		aov = (revenue / orders_count).quantize(Decimal('0.01'))
	else:
		aov = Decimal('0.00')
 
	# Conversion rate — orders / clicks
	if clicks_count > 0:
		conversion_rate = round((orders_count / clicks_count) * 100, 1)
	else:
		conversion_rate = 0.0
 
	return {
		'clicks':          clicks_count,
		'orders':          orders_count,
		'products_sold':   products_sold,
		'revenue':         revenue.quantize(Decimal('0.01')),
		'commission':      commission,
		'aov':             aov,
		'conversion_rate': conversion_rate,
	}
 



# ================================================================
# Legal Pages
# ================================================================
def terms_of_service(request):
	return render(request, 'legal/terms_of_service.html')

def privacy_policy(request):
	return render(request, 'legal/privacy_policy.html')

def cookie_policy(request):
	return render(request, 'legal/cookie_policy.html')

def cookie_policy(request):
	return render(request, 'legal/cookie_policy.html')

def shipping_policy(request):
	return render(request, 'legal/shipping_policy.html')

	