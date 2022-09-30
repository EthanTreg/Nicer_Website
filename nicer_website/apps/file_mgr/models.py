from django.db import models


# Create your models here.
class Item(models.Model):
    dir = 'dir'
    file = 'file'
    item_type = [(dir, 'Dir'), (file, 'File')]

    name = models.CharField(max_length=64)
    path = models.CharField(max_length=100, blank=True, null=True)
    type = models.CharField(max_length=4, choices=item_type, default=dir)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('name', 'path', 'type'), name='unique_name_path_type'),
            models.UniqueConstraint(
                fields=('name', 'type'),
                condition=models.Q(path__isnull=True),
                name='unique_name_type'
            ),
        ]

    def __str__(self):
        return str(self.name)
