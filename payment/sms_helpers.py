# ================================================================
# SMS NOTIFICATION HELPERS — Fulfillment-aware
# ================================================================
# Replace your existing send_order_confirmation_sms and 
# send_admin_order_alert_sms with these versions.
# ================================================================


from payment.utils import send_sms_smsportal
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def send_order_confirmation_sms(order):
    """
    Send order confirmation SMS to the customer.
    Message content differs for collection vs shipping orders.
    """
    if not order.phone:
        logger.warning(f"No phone number for order {order.id}; skipping customer SMS")
        return

    phone = _format_sa_phone(order.phone)
    if not phone:
        logger.warning(f"Invalid phone format for order {order.id}: {order.phone}")
        return

    first_name = order.full_name.split()[0] if order.full_name else 'Customer'

    # ============================================
    # Build message based on fulfillment type
    # ============================================
    if order.is_collection:
        message = _build_collection_confirmation_sms(order, first_name)
    else:
        message = _build_shipping_confirmation_sms(order, first_name)

    result = send_sms_smsportal(phone, message)
    if not result.get('success'):
        logger.error(f"Customer SMS failed for order {order.id}: {result}")


def _build_shipping_confirmation_sms(order, first_name):
    """SMS for orders being couriered to a delivery address."""
    return (
        f"Hi {first_name}, your Marvelously Green Order #{order.id} "
        f"(R{order.amount_paid}) is confirmed! "
        f"We'll SMS you tracking info once it ships (usually 1-2 days). "
        f"Delivery: 2-5 business days. "
        f"🌿 Marvelously Green"
    )


def _build_collection_confirmation_sms(order, first_name):
    """
    SMS for orders being collected from a pickup point.
    Sets expectations: "we'll tell you when ready to collect"
    Doesn't mention shipping. Names the pickup point for clarity.
    """
    # Resolve pickup point name — order.pickup_point is a dict from get_pickup_point()
    pickup = order.pickup_point
    if pickup and pickup.get('name'):
        pickup_name = pickup['name']
    else:
        # Fallback if pickup_point lookup returns None
        pickup_name = "your chosen pickup point"

    return (
        f"Hi {first_name}, your Marvelously Green Order #{order.id} "
        f"(R{order.amount_paid}) is confirmed! "
        f"You chose collection at {pickup_name}. "
        f"We'll SMS you when it's ready to collect (usually 1-2 days). "
        f"🌿 Marvelously Green"
    )


def send_ready_for_collection_sms(order):
    """
    Send "ready to collect" SMS to the customer.
    
    TRIGGER THIS MANUALLY when the parcel has actually been delivered to the
    pickup point. Options for how to trigger:
      1. Admin action in Django admin
      2. Management command: python manage.py mark_ready 43
      3. API endpoint called from your phone when you drop off
    
    (See send_ready_for_collection_sms.py for the trigger options.)
    """
    if not order.is_collection:
        logger.warning(
            f"send_ready_for_collection_sms called on non-collection order #{order.id}"
        )
        return
    
    if not order.phone:
        logger.warning(f"No phone number for order {order.id}; skipping ready SMS")
        return

    phone = _format_sa_phone(order.phone)
    if not phone:
        return

    first_name = order.full_name.split()[0] if order.full_name else 'Customer'

    # Resolve pickup point
    pickup = order.pickup_point
    if not pickup:
        logger.error(
            f"send_ready_for_collection_sms: no pickup point for order #{order.id}"
        )
        return

    pickup_name = pickup.get('name', 'the pickup point')
    pickup_address = pickup.get('address', '')
    pickup_hours = pickup.get('hours', '')

    # ============================================
    # Compose the "ready" SMS
    # This is the message the customer will SHOW to pickup point staff
    # so it needs to be clear + include order # + pickup details
    # ============================================
    parts = [
        f"Hi {first_name}, your Marvelously Green Order #{order.id} is READY to collect!"
    ]
    parts.append(f"📍 {pickup_name}")
    if pickup_address:
        parts.append(pickup_address)
    if pickup_hours:
        parts.append(f"🕐 {pickup_hours}")
    parts.append(f"Show this SMS to staff. Bring your ID.")
    parts.append("🌿 Marvelously Green")

    message = "\n".join(parts)

    result = send_sms_smsportal(phone, message)
    if not result.get('success'):
        logger.error(f"Ready-for-collection SMS failed for order {order.id}: {result}")
    else:
        logger.info(f"Ready-for-collection SMS sent for order #{order.id}")


def send_admin_order_alert_sms(order):
    """
    Alert all configured admins that a new paid order has come in.
    Now includes fulfillment tag so admins know at a glance whether
    to prepare for courier pickup or drop at a pickup point.
    """
    admin_phones = getattr(settings, 'ADMIN_SMS_PHONES', None)

    if not admin_phones:
        legacy_phone = getattr(settings, 'ADMIN_SMS_PHONE', None)
        admin_phones = [legacy_phone] if legacy_phone else []

    if isinstance(admin_phones, str):
        admin_phones = [p.strip() for p in admin_phones.split(',') if p.strip()]

    if not admin_phones:
        return

    # ============================================
    # Build fulfillment tag for the message
    # ============================================
    if order.is_collection:
        pickup = order.pickup_point
        pickup_name = pickup.get('name', 'Unknown pickup') if pickup else 'Unknown pickup'
        fulfillment_tag = f"[COLLECTION - {pickup_name}]"
    else:
        service = order.shipping_service_name or 'Courier'
        fulfillment_tag = f"[{service.upper()}]"

    message = (
        f"🔔 New Marvelously Green Order! {fulfillment_tag}\n"
        f"Order #{order.id}\n"
        f"Customer: {order.full_name}\n"
        f"Amount: R{order.amount_paid}\n"
        f"Phone: {order.phone}"
    )

    for phone in admin_phones:
        formatted = _format_sa_phone(phone)
        if not formatted:
            print(f"[SMS] Skipping invalid admin phone: {phone!r}", flush=True)
            continue

        try:
            send_sms_smsportal(formatted, message)
            print(f"[SMS] Admin alert sent to {formatted}", flush=True)
        except Exception as e:
            print(f"[SMS] Failed to send to {formatted}: {e}", flush=True)



def _format_sa_phone(phone):
	"""
	Convert South African phone number to SMSPortal format (27XXXXXXXXX).
	Accepts: 0831234567, +27831234567, 27831234567, 27 83 123 4567, etc.
	"""
	if not phone:
		return None
 
	# Strip all non-digit characters
	digits = ''.join(c for c in str(phone) if c.isdigit())
 
	if not digits:
		return None
 
	# Handle different SA formats
	if digits.startswith('27') and len(digits) == 11:
		return digits  # Already 27XXXXXXXXX
	elif digits.startswith('0') and len(digits) == 10:
		return '27' + digits[1:]  # 0XXXXXXXXX -> 27XXXXXXXXX
	elif len(digits) == 9:
		return '27' + digits  # XXXXXXXXX -> 27XXXXXXXXX
	else:
		return None  # Unknown format