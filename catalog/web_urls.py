from django.urls import path

from . import web_views as views

app_name = "library"
urlpatterns = [
    path("", views.home, name="home"),
    path("authors/", views.authors, name="authors"),
    path("authors/new/", views.author_edit, name="author-create"),
    path("authors/<int:pk>/edit/", views.author_edit, name="author-edit"),
    path("authors/<int:pk>/delete/", views.author_delete, name="author-delete"),
    path("books/", views.books, name="books"),
    path("books/new/", views.book_edit, name="book-create"),
    path("books/<int:pk>/edit/", views.book_edit, name="book-edit"),
    path("books/<int:pk>/delete/", views.book_delete, name="book-delete"),
]
