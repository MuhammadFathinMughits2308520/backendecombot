from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
import uuid

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

class ChatSession(models.Model):
    SESSION_STATUS = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('paused', 'Paused'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_sessions')
    session_id = models.CharField(max_length=100, unique=True)
    current_step = models.CharField(max_length=50, default='intro')
    status = models.CharField(max_length=20, choices=SESSION_STATUS, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'chat_sessions'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.session_id} - {self.current_step}"

class ChatMessage(models.Model):
    MESSAGE_TYPES = [
        ('user', 'User Message'),
        ('bot', 'Bot Message'),
        ('system', 'System Message'),
    ]
    
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES)
    character = models.CharField(max_length=50, blank=True, null=True)
    message_text = models.TextField()
    step_id = models.CharField(max_length=50)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Tambahan field untuk mendukung histori per kegiatan
    activity_id = models.CharField(max_length=50, default='intro')
    sequence_order = models.IntegerField(default=0)
    message_data = models.JSONField(null=True, blank=True)
    
    class Meta:
        db_table = 'chat_messages'
        ordering = ['timestamp', 'sequence_order']
        indexes = [
            models.Index(fields=['session', 'activity_id']),
            models.Index(fields=['session', 'sequence_order']),
        ]
    
    def __str__(self):
        return f"{self.message_type} - {self.step_id} - {self.timestamp}"

class UserAnswer(models.Model):
    ANSWER_TYPES = [
        ('essay', 'Essay'),
        ('discussion', 'Discussion'),
        ('challenge', 'Challenge'),
        ('creative', 'Creative'),
        ('reflective', 'Reflective'),
    ]
    
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='answers')
    question_id = models.CharField(max_length=100)
    storage_key = models.CharField(max_length=100)
    answer_text = models.TextField()
    answer_type = models.CharField(max_length=20, choices=ANSWER_TYPES)
    question_text = models.TextField()
    step_id = models.CharField(max_length=50)
    image_url = models.CharField(max_length=500, blank=True, null=True)
    is_submitted = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Tambahan field untuk mendukung histori per kegiatan
    activity_id = models.CharField(max_length=50)
    
    class Meta:
        db_table = 'user_answers'
        ordering = ['created_at']
        unique_together = ['session', 'question_id']
        indexes = [
            models.Index(fields=['session', 'activity_id']),
        ]
    
    def __str__(self):
        return f"Answer for {self.question_id} - {self.session.session_id}"

class UserProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='progress')
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='progress')
    current_kegiatan = models.CharField(max_length=50, default='kimia_hijau')
    total_answers = models.IntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_progress'
        ordering = ['-created_at']
        unique_together = ['user', 'session']
    
    def __str__(self):
        return f"Progress - {self.user.username} - {self.current_kegiatan}"

class ActivityProgress(models.Model):
    ACTIVITY_STATUS = [
        ('locked', 'Locked'),
        ('started', 'Started'),
        ('completed', 'Completed'),
    ]
    
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='activity_progress')
    activity_id = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=ACTIVITY_STATUS, default='locked')
    last_accessed = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'activity_progress'
        unique_together = ['session', 'activity_id']
        ordering = ['activity_id']
    
    def __str__(self):
        return f"{self.session.session_id} - {self.activity_id} - {self.status}"

# Model untuk menyimpan chat flow configuration
class ChatFlowConfig(models.Model):
    name = models.CharField(max_length=100, unique=True)
    flow_data = models.JSONField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'chat_flow_config'
    
    def __str__(self):
        return self.name