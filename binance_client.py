import hashlib
import hmac
import time
import requests
from config import (
    BINANCE_API_KEY, BINANCE_SECRET_KEY,
    BINANCE_FUTURES_BASE_URL, DEFAULT_HEADERS, DEFAULT_TIMEOUT
)


def get_signature(query_string):
    return hmac.new(
        BINANCE_SECRET_KEY.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def get_headers():
    headers = DEFAULT_HEADERS.copy()
    headers['X-MBX-APIKEY'] = BINANCE_API_KEY
    return headers


def get_timestamp():
    return int(round(time.time() * 1000))


def signed_request(method, endpoint, params=None, timeout=DEFAULT_TIMEOUT):
    """Make a signed request to Binance Futures API."""
    if params is None:
        params = {}

    params['timestamp'] = get_timestamp()
    query_string = '&'.join(f"{k}={v}" for k, v in params.items())
    params['signature'] = get_signature(query_string)

    url = f"{BINANCE_FUTURES_BASE_URL}{endpoint}"
    headers = get_headers()

    if method.upper() == 'GET':
        response = requests.get(url, headers=headers, params=params, timeout=timeout)
    else:
        response = requests.post(url, headers=headers, params=params, timeout=timeout)

    response.raise_for_status()
    return response.json()


def public_request(endpoint, params=None, timeout=DEFAULT_TIMEOUT):
    """Make an unsigned public request to Binance Futures API."""
    if params is None:
        params = {}
    url = f"{BINANCE_FUTURES_BASE_URL}{endpoint}"
    response = requests.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()
