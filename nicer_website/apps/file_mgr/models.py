from django.db import models


# Create your models here.
class Item(models.Model):
    dir = 'dir'
    file = 'file'
    item_type = [(dir, 'Dir'), (file, 'File')]

    name = models.CharField(max_length=64, unique=True)
    path = models.CharField(max_length=100, blank=True, null=True)
    type = models.CharField(max_length=4, choices=item_type, default=dir)

    def __str__(self):
        return str(self.name)


# class File(models.Model):
#     name = models.CharField(max_length=64, unique=True)
#     parent_id = models.ForeignKey(Directory, on_delete=models.CASCADE, related_name='files')
#
#     def __str__(self):
#         return self.name
