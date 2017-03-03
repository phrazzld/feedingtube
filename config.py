# Don't let users run arbitrary Python code in production
DEBUG = False

# Point Celery at Redis
CELERY_TASK_SERIALIZER = 'json'

# Use Gmail for our SMTP email server
MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USE_SSL = False
MAIL_DEFAULT_SENDER = 'no-reply@feedingtube.host'
