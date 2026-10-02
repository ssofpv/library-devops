from django.db import models


class Branch(models.Model):
    name = models.CharField(
        max_length=200,
        verbose_name="Название",
    )
    address = models.CharField(
        max_length=500,
        verbose_name="Адрес",
    )

    class Meta:
        ordering = ["name", "id"]
        verbose_name = "Филиал"
        verbose_name_plural = "Филиалы"

    def __str__(self):
        return self.name


class Copy(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Доступен"
        ISSUED = "issued", "Выдан"
        WITHDRAWN = "withdrawn", "Списан"

    inventory_number = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Инвентарный номер",
    )
    shelf_location = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Место хранения",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.AVAILABLE,
        verbose_name="Статус",
    )
    book = models.ForeignKey(
        "catalog.Book",
        on_delete=models.PROTECT,
        related_name="copies",
        verbose_name="Книга",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="copies",
        verbose_name="Филиал",
    )

    class Meta:
        ordering = ["id"]
        verbose_name = "Экземпляр"
        verbose_name_plural = "Экземпляры"

    def __str__(self):
        return self.inventory_number
