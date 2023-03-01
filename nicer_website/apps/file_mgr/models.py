from django.db import models


# Create your models here.
class Item(models.Model):
    dir = 'dir'
    file = 'file'
    item_type = [(dir, 'Dir'), (file, 'File')]

    name = models.CharField(max_length=64)
    path = models.CharField(max_length=100, default='/')
    type = models.CharField(max_length=4, choices=item_type, default=dir)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('name', 'path', 'type'), name='unique_name_path_type'),
        ]

        indexes = [
            models.Index(fields=['path'], name='path_idx'),
        ]

    def __str__(self):
        return str(self.name)

# create index file_mgr_item_path_idx on file_mgr_item (path)
