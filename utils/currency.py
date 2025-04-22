import os
import logging
import requests
from datetime import datetime, timedelta
from functools import lru_cache

# Cache exchange rates for 24 hours to avoid excessive API calls
CACHE_DURATION = 86400  # 24 hours in seconds

@lru_cache(maxsize=32)
def get_exchange_rate(base_currency='USD', target_currency='COP'):
    """
    Get the exchange rate between two currencies
    
    Args:
        base_currency (str): The base currency code (default: USD)
        target_currency (str): The target currency code (default: COP)
        
    Returns:
        float: The exchange rate or default value on error
    """
    # If same currency, return 1.0
    if base_currency == target_currency:
        return 1.0
    
    # Handle common combinations with fallback rates if API fails
    fallback_rates = {
        'USD-COP': 4000.0,  # Approximate USD to COP rate
        'COP-USD': 0.00025  # Approximate COP to USD rate (1/4000)
    }
    
    # Create key for rate lookup
    rate_key = f"{base_currency}-{target_currency}"
    
    try:
        # Try to get exchange rate from API - use ExchangeRate-API
        api_key = os.environ.get("EXCHANGE_RATE_API_KEY")
        
        if api_key:
            # Use Exchange Rate API with your API key
            url = f"https://v6.exchangerate-api.com/v6/{api_key}/pair/{base_currency}/{target_currency}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('result') == 'success':
                    return data.get('conversion_rate', fallback_rates.get(rate_key, 1.0))
            
            # If we get here, API call failed, log and fall back
            logging.warning(f"Exchange rate API call failed: {response.status_code}")
        else:
            # No API key provided, log and fall back
            logging.warning("No Exchange Rate API key provided, using fallback rates")
    
    except Exception as e:
        logging.error(f"Error fetching exchange rate: {str(e)}")
    
    # Fall back to approximate rates
    return fallback_rates.get(rate_key, 1.0)

def convert_currency(amount, from_currency, to_currency):
    """
    Convert an amount from one currency to another
    
    Args:
        amount (float): The amount to convert
        from_currency (str): Source currency code
        to_currency (str): Target currency code
        
    Returns:
        float: The converted amount
    """
    if from_currency == to_currency:
        return amount
    
    # Get exchange rate
    rate = get_exchange_rate(from_currency, to_currency)
    
    # Apply conversion
    return float(amount) * rate

def clear_exchange_rate_cache():
    """
    Clear the exchange rate cache
    """
    get_exchange_rate.cache_clear()
