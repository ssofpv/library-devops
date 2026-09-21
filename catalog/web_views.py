from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import override
from django.views.decorators.http import require_http_methods, require_safe

from .models import Author, Book
from .web_forms import AuthorForm, BookForm


@login_required
@require_safe
def home(request):
    return render(
        request,
        "library/home.html",
        {
            "author_count": Author.objects.count(),
            "book_count": Book.objects.count(),
        },
    )


@login_required
@require_safe
def authors(request):
    return render(request, "library/authors.html", {"authors": Author.objects.all()})


@login_required
@require_safe
def books(request):
    return render(
        request,
        "library/books.html",
        {
            "books": Book.objects.prefetch_related("authors"),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def author_edit(request, pk=None):
    author = get_object_or_404(Author, pk=pk) if pk is not None else None
    return edit(
        request,
        AuthorForm,
        author,
        "Изменить автора" if author else "Новый автор",
        "library:authors",
    )


@login_required
@require_http_methods(["GET", "POST"])
def book_edit(request, pk=None):
    book = get_object_or_404(Book, pk=pk) if pk is not None else None
    return edit(
        request, BookForm, book, "Изменить книгу" if book else "Новая книга", "library:books"
    )


def edit(request, form_class, instance, title, back):
    # Localize HTML form errors without changing the existing API language.
    with override("ru"):
        form = form_class(request.POST if request.method == "POST" else None, instance=instance)
        if request.method == "POST" and form.is_valid():
            form.save()
            messages.success(request, "Изменения сохранены.")
            return redirect(back)
        return render(request, "library/form.html", {"form": form, "title": title, "back": back})


@login_required
@require_http_methods(["GET", "POST"])
def author_delete(request, pk):
    author = get_object_or_404(Author, pk=pk)
    error = "Нельзя удалить автора, связанного с книгами." if author.books.exists() else ""
    if request.method == "POST" and not error:
        author.delete()
        messages.success(request, "Автор удалён.")
        return redirect("library:authors")
    return delete_page(request, author, "library:authors", error)


@login_required
@require_http_methods(["GET", "POST"])
def book_delete(request, pk):
    book = get_object_or_404(Book, pk=pk)
    error = ""
    if request.method == "POST":
        try:
            book.delete()
        except ProtectedError:
            error = "Нельзя удалить книгу, пока в библиотеке есть её экземпляры."
        else:
            messages.success(request, "Книга удалена.")
            return redirect("library:books")
    elif book.copies.exists():
        error = "Нельзя удалить книгу, пока в библиотеке есть её экземпляры."
    return delete_page(request, book, "library:books", error)


def delete_page(request, obj, back, error):
    return render(
        request,
        "library/delete.html",
        {
            "object": obj,
            "back": back,
            "error": error,
        },
        status=409 if request.method == "POST" and error else 200,
    )
