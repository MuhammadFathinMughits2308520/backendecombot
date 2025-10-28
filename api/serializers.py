from rest_framework import serializers
from .models import User, Feedback, ChatSession, ChatMessage, UserAnswer, UserProgress

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'password']
        extra_kwargs = {'password': {'write_only': True}}

class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = ['id', 'nama', 'email', 'pesan', 'tanggal']

class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['id', 'session', 'message_type', 'character', 'message_text', 'step_id', 'timestamp']

class UserAnswerSerializer(serializers.ModelSerializer):
    # Tambahkan field virtual untuk kompatibilitas
    activity_id = serializers.CharField(source='step_id', read_only=True)
    
    class Meta:
        model = UserAnswer
        fields = [
            'id', 'session', 'question_id', 'storage_key', 
            'answer_text', 'answer_type', 'question_text', 
            'step_id', 'activity_id', 'image_url',
            'is_submitted', 'submitted_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        
class UserProgressSerializer(serializers.ModelSerializer):
    completion_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = UserProgress
        fields = ['id', 'user', 'session', 'current_kegiatan', 'total_answers', 'completion_percentage', 'completed_at', 'created_at', 'updated_at']
    
    def get_completion_percentage(self, obj):
        return min(100, int((obj.total_answers / 9) * 100))

class ChatSessionSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    messages = ChatMessageSerializer(many=True, read_only=True)
    answers = UserAnswerSerializer(many=True, read_only=True)
    progress = UserProgressSerializer(many=True, read_only=True)
    
    class Meta:
        model = ChatSession
        fields = ['id', 'user', 'session_id', 'current_step', 'status', 'messages', 'answers', 'progress', 'created_at', 'updated_at', 'completed_at']

class CreateChatSessionSerializer(serializers.Serializer):
    session_id = serializers.CharField(max_length=100, required=True)

class ChatMessageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['message_type', 'character', 'message_text', 'step_id']

class UserAnswerCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAnswer
        fields = ['question_id', 'storage_key', 'answer_text', 'answer_type', 'question_text', 'step_id', 'image_url']