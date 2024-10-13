from pathlib import Path
import os
from dotenv import load_dotenv
import certifi

#import django_heroku
#import dj_database_url


os.environ['SSL_CERT_FILE'] = certifi.where()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


load_dotenv()

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = str(os.getenv('SECRET_KEY'))

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

#DEBUG_PROPAGATE_EXCEPTIONS = True

#ALLOWED_HOSTS = []
ALLOWED_HOSTS = [ '127.0.0.1','greenmarvelstore-production.up.railway.app', 'https://greenmarvelstore-production.up.railway.app']
CSRF_TRUSTED_ORIGINS = ['https://greenmarvelstore-production.up.railway.app']

#'127.0.0.1',

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'greenmarv',
    'cart',
    'payment',
    'paypal.standard.ipn',
    'whitenoise.runserver_nostatic',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
]

ROOT_URLCONF = 'marvel.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'cart.context_processors.cart',
            ],
        },
    },
]

WSGI_APPLICATION = 'marvel.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases
 
DATABASES = {
  'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

#DATABASES = {
#   'default': {
 #       'ENGINE': 'django.db.backends.postgresql',
 #       'NAME': 'railway',
 #       'USER': 'postgres',
 #       'PASSWORD': os.environ['DB_PASSWORD'],
 #       'HOST': 'monorail.proxy.rlwy.net',
 #       'PORT': '58664',
  #  }
#}


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = ['static/']

MEDIA_URL = 'media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

STATIC_ROOT = os.path.join(BASE_DIR,  'staticfiles')
STATICFILES_DIRS = (os.path.join(BASE_DIR, 'static'),)

# White noise static stuff
#STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
STATIC_ROOT = BASE_DIR / 'staticfiles'

#STATIC_URL = '/static/'
#STATICFILES_DIRS = [BASE_DIR / "static"]
#STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


#django_heroku.settings(locals())


PAYFAST_MERCHANT_ID =  '24614055'  #'10033849'
PAYFAST_MERCHANT_KEY = 'cybdmhnyiv7q6'  #'dmhcbmfg6r2hh'
PAYFAST_PASSPHRASE = 'Marvelousgreen2024'



# Email settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'  # Replace with your email provider's SMTP server
EMAIL_PORT = 587  # Use the appropriate port
EMAIL_HOST_USER = 'serabelekd@gmail.com'  # Your email address
EMAIL_HOST_PASSWORD = 'qlwqzmweqrnunyxc'  # Your email password
EMAIL_USE_TLS = True
#DEFAULT_FROM_EMAIL = 'serabelekd@gmail.com'
EMAIL_USE_SSL = False



