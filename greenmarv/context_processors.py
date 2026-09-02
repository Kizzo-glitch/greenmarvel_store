
from django.conf import settings
 
 
def tiktok_settings(request):
    """Expose TikTok Pixel ID to all templates."""
    return {
        'TIKTOK_PIXEL_ID': getattr(settings, 'TIKTOK_PIXEL_ID', ''),
    }
 
 
def user_pixel_data(request):
    """
    Expose normalized user data for TikTok Advanced Matching.
    Only fires for authenticated users.
    """
    if not request.user.is_authenticated:
        return {}
    
    # Phone in E.164 format (e.g. +27815473512)
    phone_e164 = ''
    try:
        # If user has ShippingAddress with phone
        if hasattr(request.user, 'shippingaddress'):
            raw_phone = request.user.shippingaddress.shipping_phone or ''
            phone_e164 = _normalize_sa_phone(raw_phone)
    except Exception:
        pass
    
    return {
        'user_phone_e164': phone_e164,
    }
 
 
def _normalize_sa_phone(raw_phone):
    """
    Normalize a South African phone number to E.164 format.
    "081 752 3336" → "+27817523336"
    "0815473512"   → "+27815473512"
    "+27815473512" → "+27815473512"
    """
    if not raw_phone:
        return ''
    
    # Strip all non-digits except leading +
    digits = ''.join(c for c in raw_phone if c.isdigit())
    
    if not digits:
        return ''
    
    # Already has country code
    if raw_phone.strip().startswith('+'):
        return '+' + digits
    
    # Local SA format starting with 0 → replace with +27
    if digits.startswith('0') and len(digits) == 10:
        return '+27' + digits[1:]
    
    # 9-digit SA mobile without leading 0
    if len(digits) == 9:
        return '+27' + digits
    
    # Unknown format — return as-is with + prefix
    return '+' + digits
 