from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth.models import User
from .models import Feedback
from django.db import IntegrityError
from .serializers import UserSerializer, FeedbackSerializer
from rest_framework_simplejwt.views import TokenVerifyView

@api_view(['POST'])
def register(request):
    try:
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            username = serializer.validated_data['username']
            password = serializer.validated_data['password']

            user = User(username=username, is_active=True)
            user.set_password(password)
            user.save()

            return Response({'message': 'User registered successfully!'})
        return Response(serializer.errors, status=400)
    except IntegrityError:
        return Response({'error': 'Username already exists'}, status=400)

from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import permission_classes

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ecombot(request):
    return Response({
        "message": f"Halo, {request.user.username}! Ini halaman profil kamu."
    })


from django.http import JsonResponse
from django.conf import settings
from .utils.cloudinary_utils import get_optimized_resources

def manifest(request, comic_slug, episode_slug):
    prefix = f"comics/{comic_slug}/{episode_slug}"
    
    # Gunakan fungsi optimized
    result = get_optimized_resources(prefix, page_width=1920)
    
    manifest = {
        'title': f"{comic_slug} - Episode {episode_slug}",
        'pages': [
            {
                'index': idx,
                'url': img['url'],  # URL sudah optimized!
                'thumbnail': img['thumbnail'],  # Untuk preview
                'alt': f"Page {idx + 1}"
            }
            for idx, img in enumerate(result['resources'])
        ]
    }
    
    return JsonResponse(manifest)


from .models import UserComicProgress

from rest_framework import status

REQUIRED_PAGE_THRESHOLD = 3  # indeks (0-based)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def comic_progress(request):
    user = request.user

    if request.method == 'GET':
        comic = request.query_params.get('comic')
        episode = request.query_params.get('episode')
        try:
            progress = UserComicProgress.objects.get(user=user, comic_slug=comic, episode_slug=episode)
            return Response({
                "finish": progress.finish,
                "allowed_page": progress.last_page,
                "last_page": progress.last_page
            })
        except UserComicProgress.DoesNotExist:
            return Response({"finish": False, "allowed_page": 0, "last_page": 0})

    # --- POST: update posisi halaman ---
    if request.method == 'POST':
        comic = request.data.get('comic')
        episode = request.data.get('episode')
        try:
            last_page = int(request.data.get('last_page', 0))
        except (TypeError, ValueError):
            return Response({"error": "Invalid last_page"}, status=status.HTTP_400_BAD_REQUEST)

        progress, created = UserComicProgress.objects.get_or_create(
            user=user,
            comic_slug=comic,
            episode_slug=episode,
            defaults={"last_page": 0, "finish": False}
        )

        # Update last_page tapi jangan turunkan progress
        if last_page > progress.last_page:
            progress.last_page = last_page

        progress.save()

        return Response({
            "saved": True,
            "finish": progress.finish,
            "last_page": progress.last_page
        })



from rest_framework import status

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def comic_mark_finish(request):
    """
    POST /api/comic-progress/finish/
    body: { "comic": "...", "episode": "...", "last_page": 3, "complete": true }
    Jika client mengirim "complete": true -> set finish=True langsung untuk user itu.
    """
    user = request.user
    comic = request.data.get("comic")
    episode = request.data.get("episode")
    last_page_body = request.data.get("last_page")
    complete_flag = bool(request.data.get("complete", False))  # <-- new flag
    force = bool(request.data.get("force", False))  # tetap ada untuk admin override if needed

    if not comic or not episode:
        return Response({"error": "Missing comic or episode"}, status=status.HTTP_400_BAD_REQUEST)

    progress, _ = UserComicProgress.objects.get_or_create(
        user=user,
        comic_slug=comic,
        episode_slug=episode,
        defaults={"last_page": 0, "finish": False}
    )

    # update last_page jika dikirim
    if last_page_body is not None:
        try:
            lp = int(last_page_body)
            if lp > progress.last_page:
                progress.last_page = lp
        except (ValueError, TypeError):
            return Response({"error": "Invalid last_page"}, status=status.HTTP_400_BAD_REQUEST)

    # Jika client menandai 'complete' -> langsung set finish True
    if complete_flag:
        progress.finish = True
        progress.save()
        return Response({"saved": True, "finish": True, "message": "Marked as complete by user"})


    # Force (untuk staff/admin)
    if force and user.is_staff:
        progress.finish = True
        progress.save()
        return Response({"saved": True, "finish": True})

    # Default behavior: require threshold
    effective_last = progress.last_page
    if last_page_body is not None:
        try:
            effective_last = max(effective_last, int(last_page_body))
        except:
            pass

    if effective_last >= REQUIRED_PAGE_THRESHOLD:
        progress.finish = True
        progress.save()
        return Response({"saved": True, "finish": True})
    else:
        return Response(
            {
                "saved": False,
                "finish": False,
                "message": "Belum mencapai batas eksplorasi. Selesaikan explorasi terlebih dahulu.",
                "required_page": REQUIRED_PAGE_THRESHOLD,
                "current_last_page": effective_last
            },
            status=status.HTTP_403_FORBIDDEN
        )

@api_view(['POST', 'GET'])
@permission_classes([AllowAny])  # ✅ tidak perlu login
def feedback_view(request):
    if request.method == 'POST':
        serializer = FeedbackSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Feedback berhasil dikirim!'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'GET':
        feedbacks = Feedback.objects.all().order_by('-tanggal')
        serializer = FeedbackSerializer(feedbacks, many=True)
        return Response(serializer.data)

from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response({"detail": "Refresh token tidak diberikan"}, status=status.HTTP_400_BAD_REQUEST)

            token = RefreshToken(refresh_token)
            token.blacklist()  # blacklist token agar tidak bisa dipakai lagi
            return Response({"detail": "Logout berhasil"}, status=status.HTTP_205_RESET_CONTENT)
        except TokenError:
            return Response({"detail": "Token tidak valid atau sudah kadaluarsa"}, status=status.HTTP_400_BAD_REQUEST)
