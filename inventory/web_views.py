from django.contrib import messages
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import override
from django.views.decorators.http import require_http_methods, require_safe

from .models import Branch, Copy
from .web_forms import BranchForm, CopyFilterForm, CopyForm


@require_safe
def branches(request):
    return render(request, "inventory_web/branches.html", {"branches": Branch.objects.all()})


@require_safe
def copies(request):
    with override("ru"):
        form = CopyFilterForm(request.GET)
        queryset = Copy.objects.select_related("book", "branch")
        valid = form.is_valid()
        if valid:
            for field in ("book", "branch"):
                value = form.cleaned_data[field]
                if value is not None:
                    queryset = queryset.filter(**{field: value})
        else:
            queryset = queryset.none()
        return render(
            request,
            "inventory_web/copies.html",
            {
                "copies": queryset,
                "filter_form": form,
            },
            status=200 if valid else 400,
        )


@require_http_methods(["GET", "POST"])
def branch_edit(request, pk=None):
    obj = get_object_or_404(Branch, pk=pk) if pk is not None else None
    return edit(
        request,
        BranchForm,
        obj,
        "Изменить филиал" if obj else "Новый филиал",
        "inventory-web:branches",
    )


@require_http_methods(["GET", "POST"])
def copy_edit(request, pk=None):
    obj = get_object_or_404(Copy, pk=pk) if pk is not None else None
    return edit(
        request,
        CopyForm,
        obj,
        "Изменить экземпляр" if obj else "Новый экземпляр",
        "inventory-web:copies",
    )


def edit(request, form_class, instance, title, back):
    with override("ru"):
        form = form_class(request.POST if request.method == "POST" else None, instance=instance)
        if request.method == "POST" and form.is_valid():
            form.save()
            messages.success(request, "Изменения сохранены.")
            return redirect(back)
        return render(
            request,
            "library/form.html",
            {
                "form": form,
                "title": title,
                "back": back,
            },
        )


@require_http_methods(["GET", "POST"])
def branch_delete(request, pk):
    obj = get_object_or_404(Branch, pk=pk)
    error = ""
    if request.method == "POST":
        try:
            obj.delete()
        except ProtectedError:
            error = "Нельзя удалить филиал, пока в нём есть экземпляры."
        else:
            messages.success(request, "Филиал удалён.")
            return redirect("inventory-web:branches")
    elif obj.copies.exists():
        error = "Нельзя удалить филиал, пока в нём есть экземпляры."
    return render(
        request,
        "library/delete.html",
        {
            "object": obj,
            "back": "inventory-web:branches",
            "error": error,
        },
        status=409 if request.method == "POST" and error else 200,
    )


@require_http_methods(["GET", "POST"])
def copy_delete(request, pk):
    obj = get_object_or_404(Copy, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Экземпляр удалён.")
        return redirect("inventory-web:copies")
    return render(
        request,
        "library/delete.html",
        {
            "object": obj,
            "back": "inventory-web:copies",
            "error": "",
        },
    )
