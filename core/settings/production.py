from .base import *
import dj_database_url
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

# 1. Disable Debug
DEBUG = False

# 2. Strict Host Checking
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["review-platform.onrender.com"])

# 3. Database (PostgreSQL on Render)
DATABASES = {
    'default': dj_database_url.config(
        default=env("DATABASE_URL", default="sqlite:///db.sqlite3"),
        conn_max_age=600
    )
}

# 4. Security Headers
# Redirect all non-HTTPS traffic to HTTPS
SECURE_SSL_REDIRECT = True
# Use HTTP Strict Transport Security (HSTS)
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
# Browser Security Headers
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY' # Prevent clickjacking
SECURE_BROWSER_XSS_FILTER = True # Enable XSS filter in older browsers
SECURE_REFERRER_POLICY = 'same-origin'

# 5. Cookie Security
# Ensure cookies are only sent over HTTPS
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# Prevent client-side JS from accessing cookies (XSS mitigation)
SESSION_COOKIE_HTTPONLY = True
# Prevent CSRF tokens from being read by scripts
CSRF_COOKIE_HTTPONLY = True
# SameSite policy
SESSION_COOKIE_SAMESITE = 'Lax'

# 6. Proxies (Cloudflare/Render)
# Trust the X-Forwarded-Proto header coming from the proxy
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# 7. Sentry (Error Tracking)
SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.1,  # Capture 10% of transactions for performance monitoring
        send_default_pii=False,
    )

# 8. Logging (No stack traces to users)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
}

# 9. Email Backend (SendGrid or similar in prod)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env("EMAIL_HOST", default="smtp.sendgrid.net")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="apikey")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")

# 10. Optional S3 media storage (persistent uploads in production)
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default="")
if AWS_STORAGE_BUCKET_NAME:
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default=None)
    AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL", default=None)
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default=None)
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default=None)
    MEDIA_URL = env("MEDIA_URL", default=f"https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/")
