from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.conf import settings
import os

from .models import Subject, Topic, Folder, Question, MockExam


def subject_folders(request, subject_slug):
    """
    Step 2: Show folders for a subject.
    Using the new Folder model structure.
    """
    subject = get_object_or_404(Subject, slug=subject_slug)
    
    # Check visibility
    if not subject.is_visible_to(request.user):
        raise Http404("Subject not found or access denied.")

    # Get folders for this subject
    # We can also prefetch topics if we want to show counts, but keeping it simple for now
    folders = Folder.objects.filter(subject=subject).order_by("order", "title")
    
    # If no folders exist yet (migration pending?), fallback to unique string values?
    # But since we migrated, we should rely on Folder objects.
    
    context = {
        "subject": subject,
        "folders": folders,  # Passing Folder objects now, template needs to handle obj.title
    }
    return render(request, "review/subject_folders.html", context)


def folder_topics(request, subject_slug, folder_name):
    """
    Step 3: Show topics in a specific folder.
    """
    subject = get_object_or_404(Subject, slug=subject_slug)
    
    # Check visibility
    if not subject.is_visible_to(request.user):
        raise Http404("Subject not found or access denied.")

    # Find the folder object
    # We use 'title' to match the URL string
    folder = get_object_or_404(Folder, subject=subject, title=folder_name)

    # Get topics in this folder
    topics = Topic.objects.filter(
        subject=subject,
        folder_ref=folder,
        is_active=True
    )

    if request.user.is_authenticated:
        topics = topics.filter(Q(is_private=False) | Q(allowed_users=request.user))
    else:
        topics = topics.filter(is_private=False)
        
    topics = topics.order_by("order", "title")

    context = {
        "subject": subject,
        "folder_name": folder_name,
        "topics": topics,
    }
    return render(request, "review/folder_topics.html", context)


def content_health(request):
    """
    Simple JSON endpoint to verify content exists in the active database.
    Useful for deployment troubleshooting.
    """
    data = {
        "subjects": Subject.objects.count(),
        "topics": Topic.objects.count(),
        "questions": Question.objects.count(),
        "mock_exams": MockExam.objects.count(),
        "debug": settings.DEBUG,
    }
    return JsonResponse(data)


def media_health(request):
    """
    Report presence of expected media files for Subjects and Blog covers.
    Helps debug 404s on /media/* in production.
    """
    subjects_missing = []
    subjects_present = 0
    try:
        for s in Subject.objects.all()[:200]:
            rel = getattr(s, "image", None)
            if rel and getattr(rel, "name", ""):
                path = os.path.join(settings.MEDIA_ROOT, rel.name)
                if os.path.exists(path):
                    subjects_present += 1
                else:
                    subjects_missing.append(rel.name)
    except Exception:
        pass

    data = {
        "serve_media": getattr(settings, "SERVE_MEDIA", False),
        "media_url": settings.MEDIA_URL,
        "media_root": str(settings.MEDIA_ROOT),
        "subjects_present": subjects_present,
        "subjects_missing_count": len(subjects_missing),
        "subjects_missing_sample": subjects_missing[:20],
    }
    return JsonResponse(data)
