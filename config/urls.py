from django.contrib import admin
from django.urls import include, path

from .views import health

urlpatterns = [
    path("", include("inventory.web_urls")),
    path("", include("catalog.web_urls")),
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("api/", include("catalog.urls")),
    path("api/", include("inventory.urls")),
]
