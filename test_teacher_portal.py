"""
Testing Script untuk Portal Guru
Jalankan dengan: python manage.py shell < test_teacher_portal.py
"""

from api.models import User, UserAnswer, ChatSession, UserProgress, UserComicProgress, ActivityProgress
from django.utils import timezone
import random

print("=" * 60)
print("🧪 Testing Teacher Portal Functions")
print("=" * 60)

# ===== 1. Create Test Data =====
print("\n📦 Creating test data...")

# Create test users if not exist
test_users = []
for i in range(1, 4):
    username = f"test_siswa_{i}"
    user, created = User.objects.get_or_create(
        username=username,
        defaults={'password': 'testpass123'}
    )
    test_users.append(user)
    if created:
        print(f"   ✅ Created user: {username}")
    else:
        print(f"   ℹ️  User exists: {username}")

# Create test comic progress
print("\n📚 Creating test comic progress...")
for user in test_users:
    comic_progress, created = UserComicProgress.objects.get_or_create(
        user=user,
        comic_slug='greenverse',
        episode_slug='episode-1',
        defaults={
            'last_page': random.randint(0, 10),
            'finish': random.choice([True, False])
        }
    )
    if created:
        print(f"   ✅ Created comic progress for {user.username}")

# Create test chat sessions
print("\n💬 Creating test chat sessions...")
for user in test_users:
    session, created = ChatSession.objects.get_or_create(
        user=user,
        session_id=f'session_{user.username}_{timezone.now().strftime("%Y%m%d")}',
        defaults={
            'current_step': random.choice(['kimia_hijau', 'kegiatan_1', 'kegiatan_2', 'kegiatan_3']),
            'status': random.choice(['active', 'completed', 'paused'])
        }
    )
    
    if created:
        print(f"   ✅ Created chat session for {user.username}")
        
        # Create test answers
        activities = ['kegiatan_1', 'kegiatan_2', 'kegiatan_3']
        for activity in activities:
            UserAnswer.objects.get_or_create(
                session=session,
                question_id=f'q_{activity}',
                defaults={
                    'storage_key': f'answer:{activity}',
                    'answer_text': f'Jawaban test untuk {activity}',
                    'answer_type': 'essay',
                    'question_text': f'Pertanyaan untuk {activity}',
                    'step_id': activity,
                    'activity_id': activity,
                    'is_submitted': True,
                    'submitted_at': timezone.now()
                }
            )
        
        # Create activity progress
        for activity in activities:
            ActivityProgress.objects.get_or_create(
                session=session,
                activity_id=activity,
                defaults={
                    'status': random.choice(['started', 'completed']),
                    'completed_at': timezone.now() if random.choice([True, False]) else None
                }
            )
        
        # Create user progress
        UserProgress.objects.get_or_create(
            user=user,
            session=session,
            defaults={
                'current_kegiatan': random.choice(activities),
                'total_answers': len(activities)
            }
        )

print("\n✅ Test data created successfully!")

# ===== 2. Test teacher_dashboard Logic =====
print("\n" + "=" * 60)
print("🧪 Testing teacher_dashboard Logic")
print("=" * 60)

for user in test_users:
    print(f"\n👤 Testing user: {user.username}")
    
    # Get comic progress
    comic_progress = UserComicProgress.objects.filter(user=user).order_by('-updated_at').first()
    if comic_progress:
        print(f"   📚 Comic: {comic_progress.comic_slug} - {comic_progress.episode_slug}")
        print(f"      Last page: {comic_progress.last_page}")
        print(f"      Status: {'Selesai' if comic_progress.finish else 'Belum Selesai'}")
    else:
        print("   ⚠️  No comic progress found")
    
    # Get chat session
    chat_session = ChatSession.objects.filter(user=user).order_by('-updated_at').first()
    if chat_session:
        print(f"   💬 Chat Session: {chat_session.session_id}")
        print(f"      Current step: {chat_session.current_step}")
        print(f"      Status: {chat_session.status}")
    else:
        print("   ⚠️  No chat session found")
    
    # Get answers
    total_answers = UserAnswer.objects.filter(
        session__user=user,
        is_submitted=True
    ).count()
    print(f"   ✍️  Total submitted answers: {total_answers}")
    
    # Get activity progress
    last_activity = ActivityProgress.objects.filter(
        session__user=user
    ).order_by('-last_accessed').first()
    if last_activity:
        print(f"   🎯 Last activity: {last_activity.activity_id}")
        print(f"      Status: {last_activity.status}")
    else:
        print("   ⚠️  No activity progress found")

# ===== 3. Test teacher_answers Logic =====
print("\n" + "=" * 60)
print("🧪 Testing teacher_answers Logic")
print("=" * 60)

# Get all answers
all_answers = UserAnswer.objects.select_related('session__user').exclude(
    session__isnull=True
).exclude(
    session__user__isnull=True
).order_by('-created_at')[:10]

print(f"\n📝 Found {all_answers.count()} answers (showing first 10):")
for idx, answer in enumerate(all_answers, 1):
    print(f"\n   {idx}. Answer ID: {answer.id}")
    print(f"      Student: {answer.session.user.username if answer.session and answer.session.user else 'Unknown'}")
    print(f"      Activity: {answer.activity_id or answer.step_id or '-'}")
    print(f"      Type: {answer.answer_type}")
    print(f"      Question: {answer.question_text[:50]}...")
    print(f"      Answer: {answer.answer_text[:50]}...")
    print(f"      Submitted: {'Yes' if answer.is_submitted else 'No'}")
    print(f"      Date: {answer.created_at.strftime('%Y-%m-%d %H:%M') if answer.created_at else '-'}")

# ===== 4. Check Data Quality =====
print("\n" + "=" * 60)
print("🔍 Checking Data Quality")
print("=" * 60)

# Check for NULL values
print("\n🔎 Checking for NULL values...")
null_session = UserAnswer.objects.filter(session__isnull=True).count()
null_activity = UserAnswer.objects.filter(activity_id__isnull=True).count()
empty_activity = UserAnswer.objects.filter(activity_id='').count()

print(f"   - Answers with NULL session: {null_session}")
print(f"   - Answers with NULL activity_id: {null_activity}")
print(f"   - Answers with empty activity_id: {empty_activity}")

if null_session > 0 or null_activity > 0 or empty_activity > 0:
    print("   ⚠️  Data quality issues found! Run fix_existing_data.py")
else:
    print("   ✅ No data quality issues found")

# Check for orphaned records
print("\n🔎 Checking for orphaned records...")
orphaned_answers = UserAnswer.objects.filter(session__isnull=True).count()
orphaned_sessions = ChatSession.objects.filter(user__isnull=True).count()

print(f"   - Orphaned answers: {orphaned_answers}")
print(f"   - Orphaned sessions: {orphaned_sessions}")

if orphaned_answers > 0 or orphaned_sessions > 0:
    print("   ⚠️  Orphaned records found! Consider cleaning up")
else:
    print("   ✅ No orphaned records found")

# ===== 5. Statistics =====
print("\n" + "=" * 60)
print("📊 Statistics")
print("=" * 60)

from django.db.models import Count, Avg

total_users = User.objects.count()
users_with_comics = UserComicProgress.objects.values('user').distinct().count()
users_with_sessions = ChatSession.objects.values('user').distinct().count()
users_with_answers = UserAnswer.objects.filter(is_submitted=True).values('session__user').distinct().count()

print(f"\n👥 Users:")
print(f"   - Total users: {total_users}")
print(f"   - Users with comic progress: {users_with_comics}")
print(f"   - Users with chat sessions: {users_with_sessions}")
print(f"   - Users with submitted answers: {users_with_answers}")

total_answers = UserAnswer.objects.filter(is_submitted=True).count()
answers_by_type = UserAnswer.objects.filter(is_submitted=True).values('answer_type').annotate(
    count=Count('id')
)

print(f"\n✍️  Answers:")
print(f"   - Total submitted answers: {total_answers}")
for item in answers_by_type:
    print(f"   - {item['answer_type']}: {item['count']}")

# Average answers per user
if users_with_answers > 0:
    avg_answers = total_answers / users_with_answers
    print(f"   - Average answers per user: {avg_answers:.2f}")

# ===== 6. Sample API Responses =====
print("\n" + "=" * 60)
print("📋 Sample API Responses")
print("=" * 60)

print("\n🔹 teacher_dashboard response format:")
print("""
{
    "siswa": "test_siswa_1",
    "user_id": 123,
    "komik": "greenverse - episode-1",
    "halaman_terakhir": 8,
    "status_komik": "Selesai",
    "chat_status": "active",
    "current_step": "kegiatan_3",
    "kegiatan_terakhir": "kegiatan_3",
    "status_kegiatan": "in_progress",
    "jawaban_terkumpul": 15,
    "terakhir_aktif": "2025-10-27 14:30"
}
""")

print("\n🔹 teacher_answers response format:")
print("""
{
    "no": 1,
    "id": 456,
    "nama_siswa": "test_siswa_1",
    "kegiatan": "kegiatan_1",
    "jenis_pertanyaan": "essay",
    "pertanyaan": "Masalah apa yang ditimbulkan oleh musim hujan?",
    "jawaban_siswa": "Banjir dan sampah...",
    "image_url": null,
    "tipe_jawaban": "essay",
    "status": "Submitted",
    "tanggal_dikirim": "2025-10-27 10:30"
}
""")

# ===== 7. Final Report =====
print("\n" + "=" * 60)
print("✅ Testing Complete!")
print("=" * 60)

print("\n🎯 Test Results:")
print(f"   ✅ Created {len(test_users)} test users")
print(f"   ✅ Dashboard logic tested")
print(f"   ✅ Answers logic tested")
print(f"   ✅ Data quality checked")

print("\n💡 Next Steps:")
print("   1. Access http://localhost:8000/api/teacher/dashboard/")
print("   2. Access http://localhost:8000/api/teacher/answers/")
print("   3. Check if data displays correctly")
print("   4. Test filtering and pagination")

print("\n🧹 Cleanup (Optional):")
print("   To delete test data, run:")
print("   User.objects.filter(username__startswith='test_siswa_').delete()")

print("\n" + "=" * 60)