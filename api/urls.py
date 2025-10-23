from django.urls import path
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
]

