from django.db import models


# Create your models here.
class Directory(models.Model):
    name = models.CharField(max_length=64, unique=True)
    parent_id = models.ForeignKey('self', on_delete=models.CASCADE, related_name='directories', null=True, blank=True)

    def __str__(self):
        return self.name


class File(models.Model):
    name = models.CharField(max_length=64, unique=True)
    parent_id = models.ForeignKey(Directory, on_delete=models.CASCADE, related_name='files')

    def __str__(self):
        return self.name
