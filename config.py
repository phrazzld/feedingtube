import os

# Don't let users run arbitrary Python code in production
DEBUG = False

# Point Celery at Redis
BROKER_URL = os.environ.get('REDISTOGO_URL', 'redis://localhost:6379/0')
CELERY_BROKER_URL = os.environ.get('REDISTOGO_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('REDISTOGO_URL', 'redis://localhost:6379/0')
CELERY_TASK_SERIALIZER = 'json'
CELERY_REDIS_MAX_CONNECTIONS = 10
BROKER_TRANSPORT_OPTIONS = {
    "max_connections": 2
}
BROKER_POOL_LIMIT = None
CELERY_IGNORE_RESULT = True
CELERY_STORE_ERRORS_EVEN_IF_IGNORED = True

# Use Gmail for our SMTP email server
MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USE_SSL = False
MAIL_DEFAULT_SENDER = 'no-reply@feedingtube.host'
