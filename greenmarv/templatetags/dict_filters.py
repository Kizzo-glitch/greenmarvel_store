"""
Custom template filters for dictionary access in Django templates.

Save this file at:
    your_app/templatetags/dict_filters.py

Where 'your_app' is one of your existing apps (e.g. 'cart', 'store', 'payment').

The 'templatetags' folder must also contain an empty __init__.py file
in order for Django to discover it.
"""

from django import template

register = template.Library()


@register.filter
def getitem(dictionary, key):
    """
    Look up a value in a dict by key.
    
    Template usage:
        {{ quantities|getitem:product.id }}
    
    Handles common edge cases:
    - Missing key returns empty string (renders as nothing in template)
    - Non-dict input returns empty string (defensive against type errors)
    - Tries both the raw key and str(key) since cart session data often
      stores product IDs as strings but objects expose them as integers
    """
    if dictionary is None:
        return ""
    
    if not hasattr(dictionary, 'get'):
        return ""
    
    # Try the key as-is first
    value = dictionary.get(key)
    if value is not None:
        return value
    
    # Try as string (common case: session stores '1', product.id is int 1)
    value = dictionary.get(str(key))
    if value is not None:
        return value
    
    # Try as int (reverse case: dict has int keys, template passes string)
    try:
        value = dictionary.get(int(key))
        if value is not None:
            return value
    except (ValueError, TypeError):
        pass
    
    return ""


@register.filter
def get_quantity(quantities, product):
    """
    Look up the quantity for a product in the cart's quantities dict.
    
    Template usage:
        {{ quantities|get_quantity:product }}
    
    More readable alternative to getitem when working with Product objects.
    """
    if quantities is None or product is None:
        return 0
    
    if not hasattr(quantities, 'get'):
        return 0
    
    # Cart session typically stores str(product.id) as the key
    return quantities.get(str(product.id), 
                          quantities.get(product.id, 0))