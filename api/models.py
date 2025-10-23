from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
from django.contrib.auth.hashers import make_password, check_password

class User(models.Model):
    username = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=255)

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def __str__(self):
        return self.username

from django.db import models
from django.contrib.auth.models import User

class UserComicProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    comic_slug = models.CharField(max_length=100)
    episode_slug = models.CharField(max_length=100)
    last_page = models.PositiveIntegerField(default=0)
    finish = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'comic_slug', 'episode_slug')

    def __str__(self):
        return f"{self.user.username} - {self.comic_slug} ({self.last_page})"
    
class Feedback(models.Model):
    nama = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    pesan = models.TextField()
    tanggal = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feedback dari {self.nama or 'Anonim'} ({self.tanggal.strftime('%Y-%m-%d')})"

