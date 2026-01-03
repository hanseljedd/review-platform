
import os
import django
import json
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.base')
django.setup()

from review.models import Subject, Topic, Folder, Question
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.urls import reverse

User = get_user_model()
# Try to get a user to simulate logged-in state (first superuser or first user)
user = User.objects.filter(is_superuser=True).first() or User.objects.first()
print(f"DEBUG: Simulating with user: {user}")

print("\n--- CHECKING SUBJECTS ---")
subjects = Subject.objects.all()
for s in subjects:
    print(f"Subject: {s.title} (ID: {s.id})")
    print(f"  is_private: {s.is_private}")
    print(f"  Topics count: {s.topics.count()}")
    
    # Check Topics
    topics = s.topics.all()
    for t in topics:
        print(f"    Topic: {t.title} (ID: {t.id}, Slug: {t.slug})")
        print(f"      is_active: {t.is_active}")
        print(f"      is_private: {t.is_private}")
        print(f"      Folder (String): '{t.folder}'")
        print(f"      Folder (FK): {t.folder_ref}")
        print(f"      Questions: {t.questions.count()}")

print("\n--- CHECKING FOLDERS ---")
folders = Folder.objects.all()
for f in folders:
    print(f"Folder: {f.title} (Subject: {f.subject.title})")

print("\n--- SIMULATING LANDING VIEW LOGIC ---")
# Replicating logic from review/views.py
base_query = Subject.objects.all()
# Simulate Anonymous
print(">> ANONYMOUS USER VIEW:")
anon_subjects = base_query.filter(is_private=False).order_by("order")[:6]
print(f"Found {anon_subjects.count()} subjects.")

preview_data = {}
for sub in anon_subjects:
    topics_query = sub.topics.filter(is_active=True).filter(is_private=False)
    
    folder_list = []
    # 1. Try Folder Model
    folders_qs = Folder.objects.filter(subject=sub).order_by("order", "title")
    print(f"  Subject '{sub.title}': Found {folders_qs.count()} Folder objects.")
    
    if folders_qs.exists():
        for folder in folders_qs:
            t_count = topics_query.filter(folder_ref=folder).count()
            print(f"    Folder '{folder.title}' (Model) has {t_count} active/public topics.")
            if t_count > 0:
                folder_list.append({"title": folder.title, "source": "model"})
    
    # 2. Fallback
    if not folder_list:
        print(f"  Subject '{sub.title}': Falling back to string field.")
        distinct_folders = topics_query.values_list("folder", flat=True).distinct()
        print(f"    Distinct string folders: {list(distinct_folders)}")
        for f_name in distinct_folders:
            display_name = f_name or "General"
            t_count = topics_query.filter(folder=f_name).count()
            print(f"    Folder '{display_name}' (String) has {t_count} topics.")
            if t_count > 0:
                folder_list.append({"title": display_name, "source": "string"})

    preview_data[sub.title] = folder_list

print("\nFINAL PREVIEW DATA (Anonymous):")
print(json.dumps(preview_data, indent=2))
