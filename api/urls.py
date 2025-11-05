from django.urls import path, include
from . import views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    # Authentication endpoints
    path('auth/register/', views.register, name='register'),
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/logout/', views.LogoutView.as_view(), name='logout'),
    
    # User endpoints
    path('ecombot/', views.ecombot, name='ecombot'),
    
    # Comic endpoints
    path('comic/manifest/<str:comic_slug>/<str:episode_slug>/', views.manifest, name='comic_manifest'),
    path('comic/progress/', views.comic_progress, name='comic_progress'),
    path('comic/progress/finish/', views.comic_mark_finish, name='comic_mark_finish'),
    
    # Feedback endpoint
    path('feedback/', views.feedback_view, name='feedback'),
    
    # Chatbot endpoints
    path('chat/start/', views.start_chat_session, name='start_chat_session'),
    path('chat/send/', views.send_chat_message, name='send_chat_message'),
    path('chat/ask/', views.ask_question, name='ask_question'),
    
    # Activity endpoints
    path('activity/submit-answer/', views.submit_activity_answer, name='submit_activity_answer'),
    path('activity/complete/', views.complete_activity, name='complete_activity'),
    path('activity/history/<str:session_id>/<str:activity_id>/', views.get_activity_history, name='get_activity_history'),
    path('session/overview/<str:session_id>/', views.get_session_overview, name='get_session_overview'),
    
    # Teacher endpoints
    path('teacher/verify-password/', views.verify_teacher_password, name='verify_teacher_password'),
    path('teacher/answers/', views.teacher_answers, name='teacher_answers'),
    path('teacher/dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/student/<str:username>/', views.teacher_student_detail, name='teacher_student_detail'),
    
    # System health endpoints
    path('health/', views.health_check, name='health_check'),
    path('debug/rag-status/', views.debug_rag_status, name='debug_rag_status'),
    path('debug/reload-rag/', views.reload_rag_system, name='reload_rag_system'),
    path('debug/reload-all/', views.reload_all_systems, name='reload_all_systems'),
    path('debug/force-rag-reload/', views.force_rag_reload, name='force_rag_reload'),
]