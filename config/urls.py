from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import include, path

from .views import health

urlpatterns = [
    path(
        "accounts/login/", LoginView.as_view(template_name="registration/login.html"), name="login"
    ),
    path("accounts/logout/", LogoutView.as_view(), name="logout"),
    path("", include("inventory.web_urls")),
    path("", include("catalog.web_urls")),
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("api/", include("catalog.urls")),
    path("api/", include("inventory.urls")),
]
