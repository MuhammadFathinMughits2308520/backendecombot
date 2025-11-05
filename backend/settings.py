# (File: backend/settings.py)

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
]

# ----------------------------------------------------
# 🧩 Aplikasi yang diinstal
# ----------------------------------------------------
INSTALLED_APPS = [
    'rest_framework',
    'corsheaders',  # <--- Pastikan corsheaders di atas
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
    'corsheaders.middleware.CorsMiddleware',  # <--- Harus di paling atas
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # <– penting untuk static di Railway
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'backend.urls'

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

# GABUNGKAN SEMUA PENGATURAN SIMPLE_JWT DI SINI
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'AUTH_HEADER_TYPES': ('Bearer',),
    
    # Pengaturan ini dari blok pertama Anda yang hilang
    'BLACKLIST_AFTER_ROTATION': True,
    'ROTATE_REFRESH_TOKENS': True,
}

# ----------------------------------------------------
# 🌐 CORS (untuk frontend React)
# ----------------------------------------------------

# Hapus atau komentari 'CORS_ALLOW_ALL_ORIGINS = True'
# CORS_ALLOW_ALL_ORIGINS = True 

# Gunakan setting yang lebih spesifik untuk produksi
CORS_ALLOWED_ORIGINS = [
    "https://greenverse.up.railway.app", # <-- Origin frontend Anda
    "http://localhost:3000",             # <-- Untuk development React lokal
    "http://localhost:5173",             # <-- Untuk development Vite lokal
]

# Tambahkan ini untuk mengizinkan frontend mengirim header/cookie
CORS_ALLOW_CREDENTIALS = True

# Izinkan header 'Authorization'
from corsheaders.defaults import default_headers
CORS_ALLOW_HEADERS = list(default_headers) + ["Authorization"]

# Percayai origin frontend untuk request POST (penting untuk keamanan)
CSRF_TRUSTED_ORIGINS = [
    "https://greenverse.up.railway.app",
]

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
STATICFILES_DIRS = []  # kosong karena file statis dikumpulkan di root saat deploy
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