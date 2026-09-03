
import hashlib
import logging
import requests
import time
from django.conf import settings

logger = logging.getLogger(__name__)


# TikTok Events API endpoint (v1.3 is current as of 2026)
TIKTOK_API_URL = "https://business-api.tiktok.com/open_api/v1.3/event/track/"


# ============================================================
# HASHING — TikTok requires SHA-256 hashed PII
# ============================================================

def _hash(value):
    """SHA-256 hash a string, normalized (lowercased, trimmed)."""
    if not value:
        return None
    return hashlib.sha256(str(value).strip().lower().encode('utf-8')).hexdigest()


def _normalize_phone(raw_phone):
    """Normalize SA phone to E.164 (+27...) for consistent hashing."""
    if not raw_phone:
        return None
    digits = ''.join(c for c in str(raw_phone) if c.isdigit())
    if not digits:
        return None
    if digits.startswith('0') and len(digits) == 10:
        return '+27' + digits[1:]
    if len(digits) == 9:
        return '+27' + digits
    if str(raw_phone).strip().startswith('+'):
        return '+' + digits
    return '+' + digits


# ============================================================
# MAIN FUNCTION — call this from payment_notify after payment confirms
# ============================================================

def track_complete_payment(order, request=None):
    """
    Fire CompletePayment to TikTok Events API for a paid order.
    
    Call from payment_notify (Payfast ITN handler) AFTER you've confirmed
    the order is genuinely paid (signature verified, amount matches, etc.)
    
    Args:
        order: Order instance with status='paid'
        request: Django request object (optional, for client_ip/user_agent)
    
    Returns:
        bool — True if event was accepted by TikTok, False on failure
    """
    if not getattr(settings, 'TIKTOK_ACCESS_TOKEN', None):
        logger.warning("TIKTOK_ACCESS_TOKEN not configured — skipping event")
        return False
    
    if order.status != 'paid':
        logger.warning(f"Order {order.id} status is '{order.status}', not 'paid' — skipping")
        return False
    
    # ============================================
    # Build user data (hashed PII for Advanced Matching)
    # ============================================
    user_data = {
        "em": [_hash(order.email)] if order.email else [],
        "ph": [_hash(_normalize_phone(order.phone))] if order.phone else [],
        "external_id": [_hash(str(order.user.id))] if order.user else [],
    }
    
    # Split name into first/last for better matching
    name_parts = (order.full_name or '').strip().split(' ', 1)
    if name_parts and name_parts[0]:
        user_data["fn"] = [_hash(name_parts[0])]
        if len(name_parts) > 1:
            user_data["ln"] = [_hash(name_parts[1])]
    
    # IP + user agent from request (improves match quality)
    if request:
        user_data["ip"] = _get_client_ip(request)
        user_data["user_agent"] = request.META.get('HTTP_USER_AGENT', '')[:500]
    
    # TikTok click ID + cookies (if present — passed through from frontend)
    if request:
        ttclid = request.COOKIES.get('ttclid') or request.session.get('ttclid')
        if ttclid:
            user_data["ttclid"] = ttclid
        
        ttp = request.COOKIES.get('_ttp')
        if ttp:
            user_data["ttp"] = ttp
    
    # Remove empty values (TikTok rejects empty arrays for some fields)
    user_data = {k: v for k, v in user_data.items() if v}
    
    # ============================================
    # Build event properties
    # ============================================
    contents = []
    try:
        for item in order.orderitem_set.all():
            contents.append({
                "content_id":   str(item.product.id),
                "content_type": "product",
                "content_name": item.product.name,
                "price":        float(item.price),
                "quantity":     int(item.quantity),
            })
    except Exception as e:
        logger.error(f"Error building contents for order {order.id}: {e}")
    
    properties = {
        "contents":     contents,
        "value":        float(order.amount_paid),
        "currency":     "ZAR",
        "order_id":     str(order.id),
    }
    
    # ============================================
    # Build the event payload
    # ============================================
    event_payload = {
        "event":           "CompletePayment",
        "event_time":      int(time.time()),
        "event_id":        f"purchase_{order.id}",  # MUST match browser pixel
        "user":            user_data,
        "properties":      properties,
        "page": {
            "url": getattr(settings, 'SITE_URL', 'https://greenmarvel.co.za'),
        },
    }
    
    request_body = {
        "event_source":     "web",
        "event_source_id":  settings.TIKTOK_PIXEL_ID,
        "data":             [event_payload],
    }
    
    # Test events mode (for debugging, set in TikTok Events Manager → Test Events)
    test_code = getattr(settings, 'TIKTOK_TEST_EVENT_CODE', '')
    if test_code:
        request_body["test_event_code"] = test_code
    
    # ============================================
    # Send to TikTok
    # ============================================
    headers = {
        "Access-Token": settings.TIKTOK_ACCESS_TOKEN,
        "Content-Type": "application/json",
    }
    
    try:
        response = requests.post(
            TIKTOK_API_URL,
            json=request_body,
            headers=headers,
            timeout=10,
        )
        
        result = response.json()
        
        if response.status_code == 200 and result.get('code') == 0:
            logger.info(
                f"TikTok CompletePayment sent for order #{order.id}: "
                f"event_id=purchase_{order.id}"
            )
            return True
        else:
            logger.error(
                f"TikTok API error for order #{order.id}: "
                f"status={response.status_code}, response={result}"
            )
            return False
    
    except requests.exceptions.Timeout:
        logger.error(f"TikTok API timeout for order #{order.id}")
        return False
    except Exception as e:
        logger.error(f"TikTok API exception for order #{order.id}: {e}")
        return False


def _get_client_ip(request):
    """Extract the real client IP, accounting for proxy headers."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # First IP in the chain is the real client
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')