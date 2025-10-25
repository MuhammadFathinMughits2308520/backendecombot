from django.urls import path, include
from . import views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    # Authentication
    path('register/', views.register, name='register'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    
    # User & Profile
    path('ecombot/', views.ecombot, name='ecombot'),
    
    # Comic System
    path('comic-progress/', views.comic_progress, name='comic_progress'),
    path('comic-progress/finish/', views.comic_mark_finish, name='comic_mark_finish'),
    path('manifest/<str:comic_slug>/<str:episode_slug>/', views.manifest, name='manifest'),
    
    # Feedback
    path('feedback/', views.feedback_view, name='feedback'),
    
    # ===== CHATBOT & RAG SYSTEM =====
    
    # RAG Question Answering
    path('ask/', views.ask_question, name='ask_question'),
    
    # Chat Session Management
    path('chat/session/start/', views.start_chat_session, name='start_chat_session'),
    path('chat/session/send/', views.send_chat_message, name='send_chat_message'),
    path('chat/session/<str:session_id>/activity/<str:activity_id>/', views.get_activity_history, name='get_activity_history'),
    path('chat/session/<str:session_id>/overview/', views.get_session_overview, name='get_session_overview'),
    
    # Activity Management
    path('chat/answer/submit/', views.submit_activity_answer, name='submit_activity_answer'),
    path('chat/activity/complete/', views.complete_activity, name='complete_activity'),
    
    # ===== DEBUG & HEALTH ENDPOINTS =====
    
    # Health check
    path('health/', views.health_check, name='health_check'),
    
    # RAG System Debug
    path('debug-rag-status/', views.debug_rag_status, name='debug_rag_status'),
    path('reload-rag/', views.reload_rag_system, name='reload_rag_system'),
    path('force-reload-rag/', views.force_rag_reload, name='force_reload_rag'),
]