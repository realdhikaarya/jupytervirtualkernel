from django.db import models
from datetime import datetime


class tbl_images_api(models.Model):
    image = models.ImageField(upload_to='images/')
