# Don't let users run arbitrary Python code in production
DEBUG = False

# Point Celery at Redis
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_TASK_SERIALIZER = 'json'
CELERY_REDIS_MAX_CONNECTIONS = 10

# Use Gmail for our SMTP email server
MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USE_SSL = False
MAIL_DEFAULT_SENDER = 'no-reply@feedingtube.host'
