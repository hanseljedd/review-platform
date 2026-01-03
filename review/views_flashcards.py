# review/views_flashcards.py
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Topic, is_feature_enabled

def flashcard_view(request, topic_slug):
    """
    Renders the flashcards UI page.
    Now enforces Privacy: 404 if user is not allowed to see this topic.
    """
    # 1. Fetch topic
    topic = get_object_or_404(Topic, slug=topic_slug)

    # 2. Check Privacy
    # (assuming we added .is_visible_to() to the model in previous step)
    if not topic.is_visible_to(request.user):
        # Return 404 to hide existence, or 403 Forbidden
        from django.http import Http404
        raise Http404("Topic not found or access denied.")

    context = {
        "topic_slug": topic.slug,
        "topic_title": topic.title,
        "subject_slug": topic.subject.slug if topic.subject else "",
        # is_premium_user expects your project to mark premium access on user.
        # Adjust the expression below to match your UserAccess check.
        "is_premium_user": (
            request.user.is_authenticated and
            # Use the proper check from your models if available, e.g. UserAccess.user_has_valid_access(request.user)
            # For now, safe fallback:
            (getattr(request.user, "has_active_premium", False) or 
             hasattr(request.user, "accesses") and request.user.accesses.filter(is_active=True).exists())
        ),
        # Feature flag name used in template/JS (string keys are project-level)
        "feature_random_enabled": is_feature_enabled("FEATURE_RANDOM_FLASHCARDS_ENABLED"),
        "page_size_default": 50,
    }
    return render(request, "review/flashcards.html", context)
