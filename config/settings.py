import os

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ON_RAILWAY = bool(os.getenv("RAILWAY_ENVIRONMENT_ID"))
DEBUG = not ON_RAILWAY
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "" if ON_RAILWAY else "local-paper-builder-development-key")
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
for host in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",") + [os.getenv("RAILWAY_PUBLIC_DOMAIN", "")]:
    if host.strip():
        ALLOWED_HOSTS.append(host.strip())
CSRF_TRUSTED_ORIGINS = [f"https://{host}" for host in ALLOWED_HOSTS[3:]]
if ON_RAILWAY:
    ALLOWED_HOSTS.append("healthcheck.railway.app")
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SECURE_REDIRECT_EXEMPT = [r"^health/$"]
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    required = ("DJANGO_SECRET_KEY", "DATABASE_URL", "R2_BUCKET_NAME", "R2_ENDPOINT_URL",
                "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise ImproperlyConfigured("Missing Railway variables: " + ", ".join(missing))
ROOT_URLCONF = "config.urls"
INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "question_bank", "paper_builder",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
if os.getenv("DATABASE_URL"):
    DATABASES["default"] = dj_database_url.config(conn_max_age=60, conn_health_checks=True)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"
TIME_ZONE = "Asia/Kolkata"
USE_TZ = True

if os.getenv("R2_BUCKET_NAME"):
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": os.environ["R2_BUCKET_NAME"],
                "endpoint_url": os.environ["R2_ENDPOINT_URL"],
                "access_key": os.environ["R2_ACCESS_KEY_ID"],
                "secret_key": os.environ["R2_SECRET_ACCESS_KEY"],
                "region_name": "auto",
                "location": "question-paper-selling",
                "file_overwrite": False,
                "default_acl": None,
                "querystring_auth": True,
            },
        },
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
