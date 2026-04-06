import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

DEBUG = os.getenv("DEBUG", "false").lower() == "true"

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "infrastructure.persistence",
    "presentation",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": dj_database_url.parse(
        os.getenv("DATABASE_URL", "sqlite:///db.sqlite3"),
        conn_max_age=600,
    )
}

FERNET_KEY = os.getenv("FERNET_KEY", "")

CSRF_TRUSTED_ORIGINS = os.getenv("CSRF_TRUSTED_ORIGINS", "http://localhost:8000").split(",")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "static/"

FINTS_PRODUCT_ID = os.getenv("FINTS_PRODUCT_ID", "")
FINTS_PRODUCT_VERSION = os.getenv("FINTS_PRODUCT_VERSION", "")

ACTUAL_API_URL = os.getenv("ACTUAL_API_URL", "http://localhost:5007/v1")
ACTUAL_API_KEY = os.getenv("ACTUAL_API_KEY", "")

TAN_SESSION_TIMEOUT_MINUTES = int(os.getenv("TAN_SESSION_TIMEOUT_MINUTES", "15"))
