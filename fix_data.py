"""
Data Migration Script untuk Portal Guru
Jalankan dengan: python manage.py shell < fix_existing_data.py
"""

from api.models import UserAnswer, ChatSession, UserProgress, ActivityProgress, UserComicProgress
from django.db.models import Q

print("=" * 60)
print("🔧 Starting Data Migration for Portal Guru")
print("=" * 60)

# ===== 1. Fix NULL activity_id in UserAnswer =====
print("\n📝 Fixing NULL activity_id in UserAnswer...")

null_activity_count = UserAnswer.objects.filter(
    Q(activity_id__isnull=True) | Q(activity_id='')
).count()

if null_activity_count > 0:
    print(f"   Found {null_activity_count} records with NULL/empty activity_id")
    
    # Update berdasarkan step_id
    updated = UserAnswer.objects.filter(
        Q(activity_id__isnull=True) | Q(activity_id='')
    ).update(activity_id='unknown')
    
    print(f"   ✅ Updated {updated} records")
    
    # Coba update yang punya step_id valid
    for answer in UserAnswer.objects.filter(activity_id='unknown').select_related('session'):
        if answer.step_id:
            answer.activity_id = answer.step_id
            answer.save()
    
    print("   ✅ Updated activity_id from step_id where available")
else:
    print("   ✅ No NULL activity_id found")

# ===== 2. Verify Data Integrity =====
print("\n🔍 Verifying data integrity...")

# Check UserAnswer dengan session NULL
orphaned_answers = UserAnswer.objects.filter(session__isnull=True).count()
if orphaned_answers > 0:
    print(f"   ⚠️  Found {orphaned_answers} UserAnswer records with NULL session")
    print("      Consider deleting these: UserAnswer.objects.filter(session__isnull=True).delete()")
else:
    print("   ✅ All UserAnswers have valid sessions")

# Check ChatSession dengan user NULL
orphaned_sessions = ChatSession.objects.filter(user__isnull=True).count()
if orphaned_sessions > 0:
    print(f"   ⚠️  Found {orphaned_sessions} ChatSession records with NULL user")
    print("      Consider deleting these: ChatSession.objects.filter(user__isnull=True).delete()")
else:
    print("   ✅ All ChatSessions have valid users")

# ===== 3. Generate Statistics =====
print("\n📊 Generating statistics...")

total_users = UserComicProgress.objects.values('user').distinct().count()
total_comic_progress = UserComicProgress.objects.count()
total_chat_sessions = ChatSession.objects.count()
total_answers = UserAnswer.objects.filter(is_submitted=True).count()

print(f"   Total unique users with comic progress: {total_users}")
print(f"   Total comic progress records: {total_comic_progress}")
print(f"   Total chat sessions: {total_chat_sessions}")
print(f"   Total submitted answers: {total_answers}")

# ===== 4. Check for Data Anomalies =====
print("\n🔎 Checking for data anomalies...")

# Users dengan banyak session
from django.db.models import Count
users_with_multiple_sessions = ChatSession.objects.values('user').annotate(
    session_count=Count('id')
).filter(session_count__gt=1)

if users_with_multiple_sessions.count() > 0:
    print(f"   ℹ️  Found {users_with_multiple_sessions.count()} users with multiple sessions")
    for item in users_with_multiple_sessions[:5]:
        print(f"      User ID {item['user']}: {item['session_count']} sessions")
else:
    print("   ✅ Each user has at most 1 session")

# Answers tanpa activity_id yang valid
invalid_activities = UserAnswer.objects.exclude(
    activity_id__in=[
        'intro', 'kimia_hijau', 'pre_kegiatan',
        'kegiatan_1', 'kegiatan_2', 'kegiatan_3', 'kegiatan_4',
        'kegiatan_5', 'kegiatan_6', 'kegiatan_7', 'completion',
        'unknown'
    ]
).count()

if invalid_activities > 0:
    print(f"   ⚠️  Found {invalid_activities} answers with unrecognized activity_id")
else:
    print("   ✅ All activity_ids are valid")

# ===== 5. Create Missing UserProgress =====
print("\n🏗️  Creating missing UserProgress records...")

from api.models import User
users_without_progress = User.objects.filter(
    progress__isnull=True
).exclude(
    chat_sessions__isnull=True
)

created_count = 0
for user in users_without_progress:
    session = ChatSession.objects.filter(user=user).first()
    if session:
        UserProgress.objects.get_or_create(
            user=user,
            session=session,
            defaults={
                'current_kegiatan': session.current_step,
                'total_answers': UserAnswer.objects.filter(session=session, is_submitted=True).count()
            }
        )
        created_count += 1

if created_count > 0:
    print(f"   ✅ Created {created_count} UserProgress records")
else:
    print("   ✅ All users with sessions have UserProgress")

# ===== 6. Final Report =====
print("\n" + "=" * 60)
print("✅ Migration Complete!")
print("=" * 60)

print("\n📋 Summary:")
print(f"   - Fixed NULL activity_id: {null_activity_count} records")
print(f"   - Total users: {total_users}")
print(f"   - Total answers: {total_answers}")
print(f"   - Total sessions: {total_chat_sessions}")

print("\n💡 Next Steps:")
print("   1. Test the teacher portal endpoints")
print("   2. Check if data is displaying correctly")
print("   3. Monitor logs for any errors")

print("\n🔗 Test URLs:")
print("   - Dashboard: GET /api/teacher/dashboard/")
print("   - Answers: GET /api/teacher/answers/")
print("   - Detail: GET /api/teacher/student/<username>/")

print("\n" + "=" * 60)