import requests
from django.conf import settings

import requests
from requests.auth import HTTPBasicAuth
import logging


from decimal import Decimal
from django.core.cache import cache


logger = logging.getLogger(__name__)


#====================================================================================================
# SMSPortal integration for sending SMS notifications (e.g., order confirmations, delivery updates)
# ===================================================================================================
def send_sms_smsportal(destination_number, message_content):
	"""
	Sends an SMS using the SMSPortal API.

	Args:
		destination_number (str): The recipient's phone number (e.g., "27831234567").
								  Ensure it's in international format without leading '+' or '00'.
		message_content (str): The content of the SMS message.

	Returns:
		dict: A dictionary containing the response from the SMSPortal API
			  or an error message.
	"""
	api_key = settings.SMS_CLIENT_ID
	api_secret = settings.SMS_API_SECRET
	sender_id = getattr(settings, 'SMS_CLIENT_ID', None) 

	if not api_key or not api_secret:
		logger.error("SMSPortal API Key or Secret is not configured in settings.py")
		return {"error": "SMS service not configured."}

	basic_auth = HTTPBasicAuth(api_key, api_secret)

	# Ensure destination number is clean (no leading + or 00)
	if destination_number.startswith('+'):
		destination_number = destination_number[1:]
	if destination_number.startswith('00'):
		destination_number = destination_number[2:]

	sms_request_payload = {
		"messages": [
			{
				"content": message_content,
				"destination": destination_number
			}
		]
	}

	# Add sender ID if configured
	if sender_id:
		sms_request_payload["messages"][0]["source"] = sender_id

	try:
		response = requests.post(
			"https://rest.smsportal.com/bulkmessages",
			auth=basic_auth,
			json=sms_request_payload
		)

		response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

		json_response = response.json()
		if response.status_code == 200:
			logger.info(f"SMS sent successfully to {destination_number}: {json_response}")
			return {"success": True, "data": json_response}
		else:
			logger.error(f"Failed to send SMS to {destination_number}. Status: {response.status_code}, Response: {json_response}")
			return {"success": False, "error": json_response}

	except requests.exceptions.HTTPError as http_err:
		logger.error(f"HTTP error sending SMS to {destination_number}: {http_err} - {response.text}")
		return {"success": False, "error": f"HTTP Error: {http_err}, Response: {response.text}"}
	except requests.exceptions.ConnectionError as conn_err:
		logger.error(f"Connection error sending SMS to {destination_number}: {conn_err}")
		return {"success": False, "error": f"Connection Error: {conn_err}. Check internet connection or SMSPortal API endpoint."}
	except requests.exceptions.Timeout as timeout_err:
		logger.error(f"Timeout error sending SMS to {destination_number}: {timeout_err}")
		return {"success": False, "error": f"Timeout Error: {timeout_err}. SMSPortal API is slow or unavailable."}
	except requests.exceptions.RequestException as req_err:
		logger.error(f"An unexpected request error occurred sending SMS to {destination_number}: {req_err}")
		return {"success": False, "error": f"Request Error: {req_err}"}
	except Exception as e:
		logger.error(f"An unexpected error occurred sending SMS to {destination_number}: {e}")
		return {"success": False, "error": f"Unexpected Error: {e}"}
	


	"""
Bob Go (formerly uAfrica) shipping rate aggregator integration.

Replaces direct Shiplogic integration with a multi-courier rate fetcher.
Returns rates from RAM, Courier Guy, Skynet, MTE, Fastway, Citi-Sprint,
Internet Express, etc. — customer picks the one they want.

Setup:
1. Sign up at https://www.bobgo.co.za
2. Get your API key from the dashboard (Settings → API)
3. Add to settings.py:
       BOBGO_API_KEY = os.environ.get('BOBGO_API_KEY')
       BOBGO_API_URL = 'https://api.bobgo.co.za/v2'
       BOBGO_TEST_MODE = False  # True for sandbox
"""


# ============================================================
# COURIER CONFIGURATION
# ============================================================

# Your warehouse / dispatch address — Bob Go needs this to calculate rates
WAREHOUSE_ADDRESS = {
    'company': 'Green Marvel (Pty) Ltd',
    'street_address': '620 Park Street',
    'local_area': 'Arcadia',
    'city': 'Pretoria',
    'zone': 'Gauteng',
    'country': 'ZA',
    'code': '0083',  # postal code
}

# Cache rate lookups for 5 minutes per address (Bob Go has rate limits)
RATE_CACHE_SECONDS = 300


# ============================================================
# MAIN FUNCTION
# ============================================================

def get_shipping_rates(delivery_address, parcels, declared_value=None):
    """
    Fetch live shipping rates from all configured couriers via Bob Go.
    
    Args:
        delivery_address: dict with keys:
            - street_address (str)
            - local_area (str)
            - city (str)
            - zone (str)        # province
            - code (str)        # postal code
            - country (str)     # 'ZA'
        parcels: list of parcel dicts with:
            - submitted_length_cm (int)
            - submitted_width_cm (int)
            - submitted_height_cm (int)
            - submitted_weight_kg (float)
        declared_value: Decimal — for insurance calculations
    
    Returns:
        List of rate dicts, sorted by price:
        [
            {
                'service_code': 'LOX',          # Use this to book later
                'service_name': 'Local Overnight',
                'courier_name': 'The Courier Guy',
                'courier_logo': 'https://...',   # Optional, for UI
                'price': Decimal('112.62'),
                'service_level_days': '1-2 days',
                'collection_cutoff': '15:00',
                'estimated_delivery_from': '2026-06-17',
                'estimated_delivery_to': '2026-06-18',
                'description': 'R 1,000.00 automatic liability included',
            },
            ...
        ]
        
        Returns empty list on API failure (caller should handle).
    """
    if not getattr(settings, 'BOBGO_API_KEY', None):
        logger.error("BOBGO_API_KEY not configured")
        return []

    # Try cache first
    cache_key = _build_cache_key(delivery_address, parcels)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached


    # Build the API request
    payload = {
        'collection_address': WAREHOUSE_ADDRESS,
        'delivery_address': {
            'street_address': delivery_address.get('street_address', ''),
            'local_area': delivery_address.get('local_area', ''),
            'city': delivery_address.get('city', ''),
            'zone': delivery_address.get('zone', ''),
            'country': delivery_address.get('country', 'ZA'),
            'code': delivery_address.get('code', ''),
        },
        'parcels': parcels,
        'declared_value': float(declared_value) if declared_value else 100.0,
    }

    headers = {
        'Authorization': f"Bearer {settings.BOBGO_API_KEY}",
        'Content-Type': 'application/json',
    }

    try:
        response = requests.post(
            f"{settings.BOBGO_API_URL}/rates",
            json=payload,
            headers=headers,
            timeout=10  # don't let a slow courier API hang the checkout page
        )
        response.raise_for_status()
        data = response.json()

    except requests.exceptions.Timeout:
        logger.warning("Bob Go API timeout — returning empty rates")
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"Bob Go API error: {e}")
        return []

    # Parse the response into our internal format
    rates = _parse_rates(data)
    
    # Cache for next request
    cache.set(cache_key, rates, RATE_CACHE_SECONDS)
    
    return rates



# ============================================================
# BOOKING (called after payment success)
# ============================================================

def create_shipment(order, selected_service_code):
    """
    Book the shipment with the courier the customer selected.
    Call this from payment_notify after payment is confirmed paid.
    
    Args:
        order: Order instance
        selected_service_code: the service_code saved when customer picked rate
    
    Returns:
        dict with 'tracking_number', 'waybill_url', 'success' keys
    """
    headers = {
        'Authorization': f"Bearer {settings.BOBGO_API_KEY}",
        'Content-Type': 'application/json',
    }

    payload = {
        'collection_address': WAREHOUSE_ADDRESS,
        'delivery_address': {
            'street_address': order.shipping_address,
            'city': order.shipping_city,
            'zone': order.shipping_province,
            'code': order.shipping_postal_code,
            'country': 'ZA',
        },
        'parcels': _parcels_from_order(order),
        'declared_value': float(order.amount_paid),
        'service_code': selected_service_code,
        'customer_reference': f"ORDER-{order.id}",
        'recipient_name': order.full_name,
        'recipient_phone': order.phone,
        'recipient_email': order.email,
    }

    try:
        response = requests.post(
            f"{settings.BOBGO_API_URL}/shipments",
            json=payload,
            headers=headers,
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        return {
            'success': True,
            'tracking_number': data.get('tracking_number'),
            'waybill_url': data.get('waybill_url'),
            'short_tracking_url': data.get('short_tracking_url'),
        }
    except Exception as e:
        logger.error(f"Bob Go booking failed for order {order.id}: {e}")
        return {'success': False, 'error': str(e)}


# ============================================================
# HELPERS
# ============================================================

def _parse_rates(api_response):
    """Convert Bob Go API response into our internal rate format, sorted by price."""
    raw_rates = api_response.get('rates', [])
    parsed = []
    
    for rate in raw_rates:
        try:
            parsed.append({
                'service_code': rate.get('service_level', {}).get('code', ''),
                'service_name': rate.get('service_level', {}).get('name', 'Standard'),
                'courier_name': rate.get('courier_name', 'Courier'),
                'courier_logo': rate.get('courier_logo_url', ''),
                'price': Decimal(str(rate.get('total_charge', 0))),
                'service_level_days': rate.get('service_level_days', ''),
                'collection_cutoff': rate.get('collection_cutoff', ''),
                'estimated_delivery_from': rate.get('min_delivery_date', ''),
                'estimated_delivery_to': rate.get('max_delivery_date', ''),
                'description': rate.get('description', ''),
            })
        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"Skipping malformed rate: {e}")
            continue
    
    # Sort by price ascending — cheapest first
    parsed.sort(key=lambda r: r['price'])
    return parsed


def _parcels_from_order(order):
    """
    Build parcel list from order items.
    Adjust dimensions based on your typical packaging.
    """
    # Single combined parcel for the whole order (simplest approach)
    # For Green Marvel: 100mL bottles, ~150g each
    total_weight_kg = 0.15 * order.cart.count_total_units()  # adjust to your model
    
    return [{
        'submitted_length_cm': 20,
        'submitted_width_cm': 15,
        'submitted_height_cm': 10,
        'submitted_weight_kg': max(0.5, total_weight_kg),  # min 0.5kg
    }]


def _build_cache_key(delivery_address, parcels):
    """Unique cache key per delivery address + parcel combination."""
    addr_key = f"{delivery_address.get('code', '')}-{delivery_address.get('city', '')}"
    weight_key = sum(p.get('submitted_weight_kg', 0) for p in parcels)
    return f"bobgo_rates:{addr_key}:{weight_key:.2f}"