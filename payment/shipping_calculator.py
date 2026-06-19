
from decimal import Decimal, ROUND_HALF_UP

"""
Shipping rate calculator with FOUR service tiers:
  COLLECTION:  Free pickup in Pretoria (Gauteng only) — Office or RRK Pharmacy
  ECONOMY:     Cheap delivery (R59-R159), 3-5 days
  STANDARD:    Mid-tier (R99-R199), 2-3 days  
  EXPRESS:     Premium (R119-R259), 1-2 days

Free shipping over R600 applies to ECONOMY tier.
COLLECTION is always free, regardless of order value, but Gauteng-only.

Dispatch address: 620 Park Street, Arcadia, Pretoria (Gauteng).
"""


# ============================================================
# ZONE DEFINITIONS
# ============================================================
PROVINCE_ZONES = {
    'Gauteng':       'local',
    'Western Cape':  'main_centre',
    'KwaZulu-Natal': 'main_centre',
    'Free State':    'main_centre',
    'Eastern Cape':  'regional',
    'Mpumalanga':    'regional',
    'North West':    'regional',
    'Limpopo':       'regional',
    'Northern Cape': 'outlying',
}


# ============================================================
# PICKUP POINTS — Collection sub-options
# ============================================================
PICKUP_POINTS = {
    'office': {
        'name':    'Marvelously Green Office',
        'address': '620 Park Street, Arcadia, Pretoria, 0083',
        'hours':   'Mon–Fri, 09:00–16:00',
        'icon':    '🏢',
        'note':    'Same-day collection available for orders placed before 12:00',
    },
    'rrk_pharmacy': {
        'name':    'RRK Pharmacy',
        'address': 'Shop 0006, Apollo Centre, 210 Du Toit Street, Arcadia, Pretoria, 0002',
        'hours':   'Extended pharmacy hours, including Saturdays',
        'icon':    '💊',
        'note':    'Best for after-hours and weekend pickup',
    },
}


# ============================================================
# RATE TABLE
# ============================================================
SHIPPING_RATES = {
    'local': {
        'collection': {'cost': Decimal('0'),   'display': Decimal('0')},     # FREE — Gauteng only
        'economy':    {'cost': Decimal('56'),  'display': Decimal('69')},
        'standard':   {'cost': Decimal('80'),  'display': Decimal('99')},
        'express':    {'cost': Decimal('95'),  'display': Decimal('119')},
    },
    'main_centre': {
        'economy':    {'cost': Decimal('75'),  'display': Decimal('89')},
        'standard':   {'cost': Decimal('100'), 'display': Decimal('119')},
        'express':    {'cost': Decimal('130'), 'display': Decimal('159')},
    },
    'regional': {
        'economy':    {'cost': Decimal('95'),  'display': Decimal('115')},
        'standard':   {'cost': Decimal('125'), 'display': Decimal('149')},
        'express':    {'cost': Decimal('160'), 'display': Decimal('189')},
    },
    'outlying': {
        'economy':    {'cost': Decimal('130'), 'display': Decimal('159')},
        'standard':   {'cost': Decimal('170'), 'display': Decimal('199')},
        'express':    {'cost': Decimal('220'), 'display': Decimal('259')},
    },
}


# ============================================================
# CONSTANTS
# ============================================================
BASE_WEIGHT_KG = Decimal('2.0')
SURCHARGE_PER_KG = Decimal('12.00')
MAX_PARCEL_WEIGHT_KG = Decimal('10')
FREE_SHIPPING_THRESHOLD = Decimal('600.00')


# ============================================================
# SERVICE METADATA
# ============================================================
SERVICE_META = {
    'collection': {
        'name':         'Collect in Pretoria',
        'icon':         '🏢',
        'description':  'Free pickup · usually ready next day',
        'subtext':      'Choose pickup point at next step',
        'eligible_for_free': True,
        'gauteng_only': True,
    },
    'economy': {
        'name':         'Economy Delivery',
        'icon':         '📮',
        'description':  '3–5 working days · Tracked',
        'subtext':      'Best value · most popular',
        'eligible_for_free': True,
        'gauteng_only': False,
    },
    'standard': {
        'name':         'Standard Delivery',
        'icon':         '📦',
        'description':  '2–3 working days · Tracked',
        'subtext':      'Reliable next-day-or-two',
        'eligible_for_free': False,
        'gauteng_only': False,
    },
    'express': {
        'name':         'Express Delivery',
        'icon':         '⚡',
        'description':  '1–2 working days · Priority · Tracked',
        'subtext':      'Fastest available',
        'eligible_for_free': False,
        'gauteng_only': False,
    },
}


# ============================================================
# MAIN FUNCTIONS
# ============================================================

def calculate_shipping(province, service_level='economy', weight_kg=None, order_total=None):
    """Calculate shipping rate for a given province and service tier."""
    if service_level not in SERVICE_META:
        raise ValueError(f"Invalid service level: {service_level}")
    
    # Collection: always free, but ONLY for Gauteng
    if service_level == 'collection':
        if province != 'Gauteng':
            raise ValueError("Collection is only available for Gauteng addresses")
        return Decimal('0.00')
    
    # Free economy shipping over threshold
    if order_total is not None and SERVICE_META[service_level]['eligible_for_free']:
        if Decimal(str(order_total)) >= FREE_SHIPPING_THRESHOLD:
            return Decimal('0.00')
    
    zone = PROVINCE_ZONES.get(province, 'regional')
    base_rate = SHIPPING_RATES[zone][service_level]['display']
    
    weight = Decimal(str(weight_kg)) if weight_kg else Decimal('1.0')
    if weight > BASE_WEIGHT_KG:
        extra_weight = weight - BASE_WEIGHT_KG
        surcharge = extra_weight * SURCHARGE_PER_KG
        base_rate += surcharge
    
    return base_rate.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def get_shipping_options(province, weight_kg=None, order_total=None):
    """
    Get all available shipping options for a province.
    
    Returns four tiers for Gauteng (Collection + Economy + Standard + Express),
    three tiers for other provinces (Economy + Standard + Express).
    
    Collection is presented first (free) so customers see the cheapest option.
    """
    options = []
    
    # Build list of service codes available for this province
    available_services = ['economy', 'standard', 'express']
    if province == 'Gauteng':
        available_services = ['collection'] + available_services
    
    for service_code in available_services:
        meta = SERVICE_META[service_code]
        price = calculate_shipping(
            province=province,
            service_level=service_code,
            weight_kg=weight_kg,
            order_total=order_total,
        )
        
        options.append({
            'service_code':    service_code,
            'service_name':    meta['name'],
            'description':     meta['description'],
            'subtext':         meta['subtext'],
            'icon':            meta['icon'],
            'price':           price,
            'is_free':         price == Decimal('0.00'),
            'is_collection':   service_code == 'collection',
            'is_recommended':  service_code == 'collection' if province == 'Gauteng' else service_code == 'economy',
            'is_cheapest':     True if service_code == 'collection' else (service_code == 'economy' and province != 'Gauteng'),
            'is_fastest':      service_code == 'express',
        })
    
    return options


def get_pickup_points():
    """Return list of pickup points for the template."""
    return [
        {'code': code, **details}
        for code, details in PICKUP_POINTS.items()
    ]


def get_pickup_point(code):
    """Look up a pickup point by code."""
    return PICKUP_POINTS.get(code)


def calculate_parcel_weight(cart_products, quantities):
    """Calculate total parcel weight from cart contents."""
    DEFAULT_PRODUCT_WEIGHT_KG = Decimal('0.15')
    PACKAGING_WEIGHT_KG = Decimal('0.20')
    
    total = PACKAGING_WEIGHT_KG
    
    for product in cart_products:
        qty = Decimal(str(quantities.get(str(product.id), 1)))
        
        if hasattr(product, 'weight') and product.weight:
            product_weight = Decimal(str(product.weight))
        else:
            product_weight = DEFAULT_PRODUCT_WEIGHT_KG
        
        total += product_weight * qty
    
    return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def get_zone_for_province(province):
    return PROVINCE_ZONES.get(province, 'regional')


def get_margin_estimate(province, service_level='economy'):
    """Estimated margin (display - cost) for internal reporting."""
    zone = PROVINCE_ZONES.get(province, 'regional')
    rates = SHIPPING_RATES[zone].get(service_level, {})
    return rates.get('display', Decimal('0')) - rates.get('cost', Decimal('0'))


def get_full_margin_report():
    """Complete margin breakdown for internal dashboards."""
    report = {}
    for zone, services in SHIPPING_RATES.items():
        report[zone] = {}
        for service, rates in services.items():
            margin = rates['display'] - rates['cost']
            margin_pct = (
                (margin / rates['cost'] * 100).quantize(Decimal('0.1'))
                if rates['cost'] > 0
                else Decimal('0')
            )
            report[zone][service] = {
                'cost':       rates['cost'],
                'display':    rates['display'],
                'margin':     margin,
                'margin_pct': margin_pct,
            }
    return report



"""
# ============================================================
# ZONE DEFINITIONS
# ============================================================
PROVINCE_ZONES3 = {
    'Gauteng':       'local',
    'Western Cape':  'main_centre',
    'KwaZulu-Natal': 'main_centre',
    'Free State':    'main_centre',
    'Eastern Cape':  'regional',
    'Mpumalanga':    'regional',
    'North West':    'regional',
    'Limpopo':       'regional',
    'Northern Cape': 'outlying',
}


# ============================================================
# PICKUP POINTS — Collection sub-options
# ============================================================
PICKUP_POINTS3 = {
    'office': {
        'name':    'Marvelously Green Office',
        'address': '620 Park Street, Arcadia, Pretoria, 0083',
        'hours':   'Mon–Fri, 09:00–16:00',
        'icon':    '🏢',
        'note':    'Same-day collection available for orders placed before 12:00',
    },
    'rrk_pharmacy': {
        'name':    'RRK Pharmacy',
        'address': 'Shop 0006, Apollo Centre, 210 Du Toit Street, Arcadia, Pretoria, 0002',
        'hours':   'Extended pharmacy hours, including Saturdays',
        'icon':    '💊',
        'note':    'Best for after-hours and weekend pickup',
    },
}
 

# ============================================================
# RATE TABLE — THREE TIERS
# ============================================================
# Format: 'cost' = actual Bob Go dashboard cost, 'display' = customer price
# Update quarterly against real Bob Go invoices.

SHIPPING_RATES3 = {
    'local': {
        'collection': {'cost': Decimal('0'), 'display': Decimal('0')},
        'economy':  {'cost': Decimal('56'),  'display': Decimal('65')},
        'standard': {'cost': Decimal('80'),  'display': Decimal('99')},
        'express':  {'cost': Decimal('95'),  'display': Decimal('119')},
    },
    'main_centre': {
        'economy':  {'cost': Decimal('75'),  'display': Decimal('89')},
        'standard': {'cost': Decimal('100'), 'display': Decimal('119')},
        'express':  {'cost': Decimal('130'), 'display': Decimal('159')},
    },
    'regional': {
        'economy':  {'cost': Decimal('95'),  'display': Decimal('115')},
        'standard': {'cost': Decimal('125'), 'display': Decimal('149')},
        'express':  {'cost': Decimal('160'), 'display': Decimal('189')},
    },
    'outlying': {
        'economy':  {'cost': Decimal('130'), 'display': Decimal('159')},
        'standard': {'cost': Decimal('170'), 'display': Decimal('199')},
        'express':  {'cost': Decimal('220'), 'display': Decimal('259')},
    },
}


# ============================================================
# WEIGHT & THRESHOLDS
# ============================================================
BASE_WEIGHT_KG2 = Decimal('2.0')
SURCHARGE_PER_KG2 = Decimal('12.00')
MAX_PARCEL_WEIGHT_KG2 = Decimal('10')
FREE_SHIPPING_THRESHOLD2 = Decimal('600.00')


# ============================================================
# SERVICE METADATA (for display)
# ============================================================
SERVICE_META2 = {
    'collection': {
        'name':        'Collect in Pretoria',
        'icon':        '🏢',
        'description': 'Free pickup · usually ready next day',
        'subtext':     'Choose office or RRK Pharmacy at next step',
        'eligible_for_free': True,  # always free
    },

    'economy': {
        'name':        'Economy Delivery',
        'icon':        '📮',
        'description': '4–7 working days · Tracked',
        'subtext':     'Best value · most popular',
        'eligible_for_free': True,
    },
    'standard': {
        'name':        'Standard Delivery',
        'icon':        '📦',
        'description': '3–5 working days · Tracked',
        'subtext':     'Reliable next 3-to-5 days',
        'eligible_for_free': False,
    },
    'express': {
        'name':        'Express Delivery',
        'icon':        '⚡',
        'description': '2–3 working days · Priority · Tracked',
        'subtext':     'Fastest available',
        'eligible_for_free': False,
    },
}


# ============================================================
# MAIN FUNCTIONS
# ============================================================

def calculate_shipping2(province, service_level='economy', weight_kg=None, order_total=None):
 
    if service_level not in ('economy', 'standard', 'express'):
        raise ValueError(f"Invalid service level: {service_level}")
    
    # Free shipping for orders over threshold (economy tier only)
    if order_total is not None and SERVICE_META[service_level]['eligible_for_free']:
        if Decimal(str(order_total)) >= FREE_SHIPPING_THRESHOLD:
            return Decimal('0.00')
    
    # Determine zone
    zone = PROVINCE_ZONES.get(province, 'regional')
    
    # Look up base rate
    base_rate = SHIPPING_RATES[zone][service_level]['display']
    
    # Add weight surcharge if applicable
    weight = Decimal(str(weight_kg)) if weight_kg else Decimal('1.0')
    if weight > BASE_WEIGHT_KG:
        extra_weight = weight - BASE_WEIGHT_KG
        surcharge = extra_weight * SURCHARGE_PER_KG
        base_rate += surcharge
    
    return base_rate.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def get_shipping_options2(province, weight_kg=None, order_total=None):
  
    options = []
    
    for service_code in ('economy', 'standard', 'express'):
        meta = SERVICE_META[service_code]
        price = calculate_shipping(
            province=province,
            service_level=service_code,
            weight_kg=weight_kg,
            order_total=order_total,
        )
        
        options.append({
            'service_code':    service_code,
            'service_name':    meta['name'],
            'description':     meta['description'],
            'subtext':         meta['subtext'],
            'icon':            meta['icon'],
            'price':           price,
            'is_free':         price == Decimal('0.00'),
            'is_recommended':  service_code == 'economy',
            'is_cheapest':     service_code == 'economy',
            'is_fastest':      service_code == 'express',
        })
    
    return options


def calculate_parcel_weight3(cart_products, quantities):
   
    DEFAULT_PRODUCT_WEIGHT_KG = Decimal('0.15')
    PACKAGING_WEIGHT_KG = Decimal('0.20')
    
    total = PACKAGING_WEIGHT_KG
    
    for product in cart_products:
        qty = Decimal(str(quantities.get(str(product.id), 1)))
        
        if hasattr(product, 'weight') and product.weight:
            product_weight = Decimal(str(product.weight))
        else:
            product_weight = DEFAULT_PRODUCT_WEIGHT_KG
        
        total += product_weight * qty
    
    return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def get_zone_for_province(province):
    
    return PROVINCE_ZONES.get(province, 'regional')


def get_margin_estimate(province, service_level='economy'):

    zone = PROVINCE_ZONES.get(province, 'regional')
    rates = SHIPPING_RATES[zone][service_level]
    return rates['display'] - rates['cost']


def get_full_margin_report():
  
    report = {}
    for zone, services in SHIPPING_RATES.items():
        report[zone] = {}
        for service, rates in services.items():
            report[zone][service] = {
                'cost':    rates['cost'],
                'display': rates['display'],
                'margin':  rates['display'] - rates['cost'],
                'margin_pct': ((rates['display'] - rates['cost']) / rates['cost'] * 100).quantize(Decimal('0.1')),
            }
    return report

"""






