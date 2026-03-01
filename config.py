import os

# Binance API
BINANCE_API_KEY = os.environ.get('BINANCE_API_KEY', '')
BINANCE_SECRET_KEY = os.environ.get('BINANCE_SECRET_KEY', '')

# Binance API Base URLs
BINANCE_FUTURES_BASE_URL = 'https://fapi.binance.com'
BINANCE_SPOT_BASE_URL = 'https://api.binance.com'

# Email (163 SMTP)
EMAIL_SENDER = os.environ.get('EMAIL_SENDER', '')
EMAIL_SMTP_PASSWORD = os.environ.get('EMAIL_SMTP_PASSWORD', '')
EMAIL_RECIPIENT = os.environ.get('EMAIL_RECIPIENT', '')
EMAIL_SMTP_SERVER = os.environ.get('EMAIL_SMTP_SERVER', 'smtp.163.com')
EMAIL_SMTP_PORT = int(os.environ.get('EMAIL_SMTP_PORT', '465'))

# HTTP
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36',
}
DEFAULT_TIMEOUT = 15  # seconds

# Default trading pair
DEFAULT_SYMBOL = 'BTCUSDT'


def validate_binance_config():
    if not BINANCE_API_KEY or not BINANCE_SECRET_KEY:
        raise ValueError(
            "Binance API credentials not set. "
            "Set BINANCE_API_KEY and BINANCE_SECRET_KEY environment variables."
        )


def validate_email_config():
    if not EMAIL_SENDER or not EMAIL_SMTP_PASSWORD:
        raise ValueError(
            "Email credentials not set. "
            "Set EMAIL_SENDER and EMAIL_SMTP_PASSWORD environment variables."
        )
