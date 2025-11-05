from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView
from . import views


urlpatterns = [
    path('register/', views.register),
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('ecombot/', views.ecombot),
    path('comics/<str:comic_slug>/<str:episode_slug>/manifest.json', views.manifest),
    path('comic-progress/', views.comic_progress, name='comic_progress'),
    path('comic-progress/finish/', views.comic_mark_finish, name='comic_mark_finish'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('feedback/', views.feedback_view, name='feedback'),
    path('teacher/verify-password/', views.verify_teacher_password, name='verify_teacher_password'),
    path("teacher/answers/", views.teacher_answers, name="teacher_answers"),
    path("teacher/dashboard/", views.teacher_dashboard, name="teacher_dashboard"),
    path("teacher/student/<str:username>/", views.teacher_student_detail, name="teacher_student_detail"),

    path('ask/', views.ask_question, name='ask_question'),
    
    # Chat Session Management
    path('chat/session/start/', views.start_chat_session, name='start_chat_session'),
    path('chat/session/send/', views.send_chat_message, name='send_chat_message'),
    path('chat/session/<str:session_id>/activity/<str:activity_id>/', views.get_activity_history, name='get_activity_history'),
    path('chat/session/<str:session_id>/overview/', views.get_session_overview, name='get_session_overview'),
    
    # Activity Management
    path('chat/answer/submit/', views.submit_activity_answer, name='submit_activity_answer'),
    path('chat/activity/complete/', views.complete_activity, name='complete_activity'),
    # path('chat/flow/', views.get_chat_flow, name='get_chat_flow'),
    path('chat/session/<str:session_id>/overview/', views.get_session_overview, name='get_session_overview'),
    path('chat/session/<str:session_id>/activity/<str:activity_id>/', views.get_activity_history, name='get_activity_history'),

    
    # ===== DEBUG & HEALTH ENDPOINTS =====
    
    # Health check
    path('health/', views.health_check, name='health_check'),
    
    # RAG System Debug
    path('debug-rag-status/', views.debug_rag_status, name='debug_rag_status'),
    path('reload-rag/', views.reload_rag_system, name='reload_rag_system'),
    path('force-reload-rag/', views.force_rag_reload, name='force_reload_rag'),

]