from pathlib import Path
from datetime import timedelta
import os
from dotenv import load_dotenv
import dj_database_url

# ----------------------------------------------------
# 🔧 Path dasar
# ----------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# ----------------------------------------------------
# 🔒 Keamanan yang digunakan
# ----------------------------------------------------
load_dotenv()  # ambil dari file .env (lokal)

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-devkey')
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    ".railway.app",
    "greenverse.up.railway.app",
    "backendecombot-production.up.railway.app",
]

# ----------------------------------------------------
# 🧩 Aplikasi yang diinstal
# ----------------------------------------------------
INSTALLED_APPS = [
    'rest_framework',
    'corsheaders',  # HARUS di atas lainnya
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'api',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
]

# ----------------------------------------------------
# ⚙️ Middleware
# ----------------------------------------------------
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # HARUS di paling atas
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'backend.urls'

# ----------------------------------------------------
# 🌐 CORS SETTINGS YANG DIPERBAIKI
# ----------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = False  # Non-aktifkan untuk security
CORS_ALLOWED_ORIGINS = [
    "https://greenverse.up.railway.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",  # Vite dev server
    "http://127.0.0.1:5173",
]

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# ----------------------------------------------------
# 🎨 Template
# ----------------------------------------------------
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'

# ----------------------------------------------------
# 🗄️ Database (otomatis menyesuaikan Railway atau lokal)
# ----------------------------------------------------
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL', 'sqlite:///db.sqlite3'),
        conn_max_age=600
    )
}

# ----------------------------------------------------
# 🔑 Auth & JWT
# ----------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    )
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'AUTH_HEADER_TYPES': ('Bearer',),
    'BLACKLIST_AFTER_ROTATION': True,
    'ROTATE_REFRESH_TOKENS': True,
}

# ----------------------------------------------------
# 🌍 Internasionalisasi
# ----------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Jakarta'
USE_I18N = True
USE_TZ = True

# ----------------------------------------------------
# 📁 Static Files
# ----------------------------------------------------
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = []
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ----------------------------------------------------
# 🧩 Cloudinary (jika kamu pakai)
# ----------------------------------------------------
CLOUD_NAME = os.getenv("CLOUD_NAME")
CLOUD_API_KEY = os.getenv("CLOUD_API_KEY")
CLOUD_API_SECRET = os.getenv("CLOUD_API_SECRET")

# ----------------------------------------------------
# 🪪 Default PK
# ----------------------------------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'