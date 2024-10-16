from rest_framework import serializers
from .models import tbl_images_api
 

class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = tbl_images_api
        fields = ['image']
