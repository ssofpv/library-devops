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
