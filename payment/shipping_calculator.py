"""
Expanded shipping rate calculator for Green Marvel.

Three service tiers based on Bob Go dashboard actual costs:

  ECONOMY:  Cheapest option, slower delivery (MTE, RAM Economy, Internet Express)
            Actual cost via Bob Go: R45-R75 (Gauteng), R65-R95 (other provinces)
            
  STANDARD: Balanced — Bob Go's mid-tier options
            (Courier Guy Local Overnight, Fastway, Skynet Economy)
            Actual cost via Bob Go: R75-R105 (Gauteng), R95-R130 (other provinces)
  
  EXPRESS:  Premium next-day service
            (RAM Next Day, Skynet Express, Internet Express Local Express)
            Actual cost via Bob Go: R95-R130 (Gauteng), R125-R180 (other provinces)

Each tier has its own rate by zone, calibrated against your Bob Go invoices.
Free shipping applies to ECONOMY tier on orders over R600.

Dispatch address: 620 Park Street, Arcadia, Pretoria (Gauteng).
"""

from decimal import Decimal, ROUND_HALF_UP


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
# RATE TABLE — THREE TIERS
# ============================================================
# Format: 'cost' = actual Bob Go dashboard cost, 'display' = customer price
# Update quarterly against real Bob Go invoices.

SHIPPING_RATES = {
    'local': {
        'economy':  {'cost': Decimal('56'),  'display': Decimal('69')},
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
BASE_WEIGHT_KG = Decimal('2.0')
SURCHARGE_PER_KG = Decimal('12.00')
MAX_PARCEL_WEIGHT_KG = Decimal('10')
FREE_SHIPPING_THRESHOLD = Decimal('600.00')


# ============================================================
# SERVICE METADATA (for display)
# ============================================================
SERVICE_META = {
    'economy': {
        'name':        'Economy Delivery',
        'icon':        '📮',
        'description': '5–7 working days · Tracked',
        'subtext':     'Best value · most popular',
        'eligible_for_free': True,
    },
    'standard': {
        'name':        'Standard Delivery',
        'icon':        '📦',
        'description': '3–5 working days · Tracked',
        'subtext':     'Reliable next-day-or-two',
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

def calculate_shipping(province, service_level='economy', weight_kg=None, order_total=None):
    """
    Calculate the shipping rate to display to a customer.
    """
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


def get_shipping_options(province, weight_kg=None, order_total=None):
    """
    Get all three service tiers as a list of dicts for the template.
    """
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
    """Helper: returns the zone name for a given province."""
    return PROVINCE_ZONES.get(province, 'regional')


def get_margin_estimate(province, service_level='economy'):
    """Returns estimated margin (display - cost) for a given province and service."""
    zone = PROVINCE_ZONES.get(province, 'regional')
    rates = SHIPPING_RATES[zone][service_level]
    return rates['display'] - rates['cost']


def get_full_margin_report():
    """Returns a complete margin breakdown for all zones and tiers."""
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
Custom shipping rate calculator for Green Marvel.

Rationale:
- Operational address: 620 Park Street, Arcadia, Pretoria (Gauteng)
- Actual shipping is booked via Bob Go dashboard manually
- This module sets customer-facing rates based on real Bob Go costs + margin
- No third-party API call needed at checkout (faster, cheaper, more reliable)

Maintenance:
- Review SHIPPING_RATES table quarterly against actual Bob Go invoices
- Update prices when courier base rates change (usually annually)
"""


# ============================================================
# ZONE DEFINITIONS
# ============================================================
# Local = same province as dispatch (Gauteng/Pretoria)
# Main centres = major metros with strong courier infrastructure
# Regional = secondary cities and towns
# Outlying = remote, farm, or low-coverage areas

PROVINCE_ZONES2 = {
    'Gauteng':       'local',         # Dispatch location — fastest, cheapest
    'Western Cape':  'main_centre',   # Cape Town, surrounds
    'KwaZulu-Natal': 'main_centre',   # Durban, surrounds
    'Free State':    'main_centre',   # Bloemfontein
    'Eastern Cape':  'regional',      # Port Elizabeth, East London, Mthatha
    'Mpumalanga':    'regional',      # Nelspruit, Witbank
    'North West':    'regional',      # Rustenburg, Mahikeng
    'Limpopo':       'regional',      # Polokwane
    'Northern Cape': 'outlying',      # Kimberley, sparse coverage
}


# ============================================================
# RATE TABLE
# ============================================================
# All prices in ZAR
# Base rates assume parcel weight ≤ 2 kg
# 'cost' = approximate amount you pay via Bob Go dashboard
# 'display' = what customer pays at checkout (cost + margin)

SHIPPING_RATES2 = {
    'local': {
        'standard': {'cost': Decimal('45'),  'display': Decimal('59')},
        'express':  {'cost': Decimal('70'),  'display': Decimal('89')},
    },
    'main_centre': {
        'standard': {'cost': Decimal('65'),  'display': Decimal('79')},
        'express':  {'cost': Decimal('95'),  'display': Decimal('119')},
    },
    'regional': {
        'standard': {'cost': Decimal('85'),  'display': Decimal('99')},
        'express':  {'cost': Decimal('125'), 'display': Decimal('149')},
    },
    'outlying': {
        'standard': {'cost': Decimal('120'), 'display': Decimal('149')},
        'express':  {'cost': Decimal('180'), 'display': Decimal('219')},
    },
}


# ============================================================
# WEIGHT SURCHARGE
# ============================================================
# Most orders are 1-2 hero products + packaging = under 1 kg
# Heavier orders (3+ products, combos) trigger surcharges

BASE_WEIGHT_KG2 = Decimal('2.0')      # rates above cover up to this weight
SURCHARGE_PER_KG2 = Decimal('12.00')  # rand per extra kg
MAX_PARCEL_WEIGHT_KG2 = Decimal('10') # split into 2 parcels above this


# ============================================================
# FREE SHIPPING THRESHOLD
# ============================================================
FREE_SHIPPING_THRESHOLD2 = Decimal('600.00')


# ============================================================
# MAIN FUNCTIONS
# ============================================================

def calculate_shipping2(province, service_level='standard', weight_kg=None, order_total=None):
    """
    Calculate the shipping rate to display to a customer.
    
    Args:
        province: str — South African province name (case-insensitive)
        service_level: 'standard' or 'express'
        weight_kg: float or Decimal — total parcel weight (default 1.0)
        order_total: Decimal — order subtotal, used for free shipping check
    
    Returns:
        Decimal — rate to charge customer (R0.00 if qualifies for free shipping)
    
    Raises:
        ValueError if service_level invalid
    """
    if service_level not in ('standard', 'express'):
        raise ValueError(f"Invalid service level: {service_level}")
    
    # Free shipping for orders over the threshold (standard service only)
    if order_total is not None and service_level == 'standard':
        if Decimal(str(order_total)) >= FREE_SHIPPING_THRESHOLD:
            return Decimal('0.00')
    
    # Determine zone
    zone = PROVINCE_ZONES.get(province, 'regional')  # default = regional
    
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
    """
    Get all available shipping options for the customer to choose from.
    Returns a list suitable for rendering as radio cards in checkout.
    
    Args:
        province: str
        weight_kg: float or Decimal
        order_total: Decimal — for free shipping check
    
    Returns:
        List of dicts:
        [
            {
                'service_code': 'standard',
                'service_name': 'Standard Delivery',
                'description': '3-5 working days',
                'price': Decimal('59.00'),
                'is_free': False,
                'is_recommended': True,
            },
            {
                'service_code': 'express',
                'service_name': 'Express Delivery',
                'description': '1-2 working days',
                'price': Decimal('89.00'),
                'is_free': False,
                'is_recommended': False,
            },
        ]
    """
    standard_price = calculate_shipping(
        province=province,
        service_level='standard',
        weight_kg=weight_kg,
        order_total=order_total,
    )
    express_price = calculate_shipping(
        province=province,
        service_level='express',
        weight_kg=weight_kg,
        order_total=None,  # Express never free regardless of order total
    )
    
    return [
        {
            'service_code': 'standard',
            'service_name': 'Standard Delivery',
            'description': '3-5 working days · Tracked',
            'price': standard_price,
            'is_free': standard_price == Decimal('0.00'),
            'is_recommended': True,
            'icon': '📦',
        },
        {
            'service_code': 'express',
            'service_name': 'Express Delivery',
            'description': '1-2 working days · Tracked · Priority',
            'price': express_price,
            'is_free': False,
            'is_recommended': False,
            'icon': '⚡',
        },
    ]


def calculate_parcel_weight2(cart_products, quantities):
    """
    Calculate total parcel weight from cart contents.
    
    Args:
        cart_products: queryset of Product instances
        quantities: dict mapping str(product_id) → qty
    
    Returns:
        Decimal weight in kg (minimum 0.3 kg to account for packaging)
    """
    DEFAULT_PRODUCT_WEIGHT_KG = Decimal('0.15')  # 100mL bottle ~150g
    PACKAGING_WEIGHT_KG = Decimal('0.20')        # box, padding, label
    
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
    """Helper: returns the zone name for a given province (for reporting/debugging)."""
    return PROVINCE_ZONES.get(province, 'regional')


def get_margin_estimate(province, service_level='standard'):
    """
    Returns estimated margin (display - cost) for a given province and service.
    For internal reporting only — never expose to customers.
    """
    zone = PROVINCE_ZONES.get(province, 'regional')
    rates = SHIPPING_RATES[zone][service_level]
    return rates['display'] - rates['cost']