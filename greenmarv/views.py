from django.shortcuts import render, redirect
from .models import Product, Profile
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .forms import SignUpForm, UpdateUserForm, ChangePasswordForm, UserInfoForm
from django import forms
from django.db.models import Q
import json
from cart.cart import Cart

from payment.forms import ShippingForm
from payment.models import ShippingAddress
from django.utils import timezone



"""
Updated register_user + update_info views with name/email prefill.

Flow:
1. User registers with first_name, last_name, email
2. We immediately create a ShippingAddress with those fields prefilled
3. They land on update_info — see their name & email already filled in
4. They only need to add phone, address, city, province, postal code
"""

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

			# Do some shopping cart stuff
			#current_user = Profile.objects.get(user__id=request.user.id)


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

			#messages.success(request, ('You have been logged in'))
			return redirect('home')
		else:
			messages.success(request, ('There was an Error, please try again'))
			return redirect('login')

	else:
		return render(request, 'login.html', {})


def register_user2(request):
	if request.method == 'POST':
		form = SignUpForm(request.POST)
		if form.is_valid():
			form.save()
			username = form.cleaned_data['username']
			password = form.cleaned_data['password1']

			user = authenticate(username=username, password=password)
			login(request, user)
			messages.success(request, 'You have created your Username Successfully - Please complete the form below')
			return redirect('update_info')
		else:
			messages.error(request, 'Oops, there was a problem registering. Please correct the errors below.')
			return render(request, 'register.html', {'form': form})  
	else:
		form = SignUpForm()
		return render(request, 'register.html', {'form': form})

def update_info2(request):
	if request.user.is_authenticated:
		# Get Current User
		current_user = Profile.objects.get(user__id=request.user.id)
		# Get Current User's Shipping Info
		shipping_user = ShippingAddress.objects.get(user__id=request.user.id)
		
		# Get original User Form
		form = UserInfoForm(request.POST or None, instance=current_user)
		# Get User's Shipping Form
		shipping_form = ShippingForm(request.POST or None, instance=shipping_user)		
		if form.is_valid() or shipping_form.is_valid():
			# Save original form
			form.save()
			# Save shipping form
			shipping_form.save()

			messages.success(request, "Your Info Has Been Updated!!")
			return redirect('shop')
		return render(request, "update_info.html", {'form':form, 'shipping_form':shipping_form})
	else:
		messages.success(request, "You Must Be Logged In To Access That Page!!")
		return redirect('home')


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
	products = Product.objects.filter(name__icontains="combo")

	#products = Product.objects.all()
	return render(request, 'home.html', {
		'products':products, 
		"now": timezone.now(),})

def product(request,pk):
	product = Product.objects.get(id=pk)
	return render(request, 'product.html', {'product':product})

def shop_all(request):
    # Fetch all products, ordered by name or date added
    all_products = Product.objects.all().order_by("-is_sale")
    return render(request, 'shop.html', {'products': all_products})

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

	