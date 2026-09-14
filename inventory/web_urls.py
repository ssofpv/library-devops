from django.urls import path

from . import web_views as views

app_name = "inventory-web"
urlpatterns = [
    path("branches/", views.branches, name="branches"),
    path("branches/new/", views.branch_edit, name="branch-create"),
    path("branches/<int:pk>/edit/", views.branch_edit, name="branch-edit"),
    path("branches/<int:pk>/delete/", views.branch_delete, name="branch-delete"),
    path("copies/", views.copies, name="copies"),
    path("copies/new/", views.copy_edit, name="copy-create"),
    path("copies/<int:pk>/edit/", views.copy_edit, name="copy-edit"),
    path("copies/<int:pk>/delete/", views.copy_delete, name="copy-delete"),
]
