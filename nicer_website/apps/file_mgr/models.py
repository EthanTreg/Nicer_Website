"""
Models for the file_mgr database
"""
from django.db import models


class Item(models.Model):
    """
    Model for the file manager database to contain the files and directories with their paths
    """
    dir = 'dir'
    file = 'file'
    item_type = [(dir, 'Dir'), (file, 'File')]

    name = models.CharField(max_length=64)
    path = models.CharField(max_length=100, default='/')
    type = models.CharField(max_length=4, choices=item_type, default=dir)

    class Meta:
        """
        Metadata for the file manager model to prevent duplicate entries with the same name, path,
        and type, as well as creating an index on the path column to increase indexing performance
        """
        constraints = [
            models.UniqueConstraint(fields=('name', 'path', 'type'), name='unique_name_path_type'),
        ]

        indexes = [
            models.Index(fields=['path'], name='path_idx'),
        ]

    def __str__(self):
        return str(self.name)

# create index file_mgr_item_path_idx on file_mgr_item (path)
