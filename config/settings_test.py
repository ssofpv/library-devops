from . import settings as base_settings

globals().update(
    {name: getattr(base_settings, name) for name in dir(base_settings) if name.isupper()}
)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
