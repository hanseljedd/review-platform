# review/views.py
import logging
import os
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from .models import Subject, Topic, Folder, UserAccess, is_feature_enabled, ReviewFile, MockExam, ExamSession, Question
from blog.models import BlogPost
from datetime import timedelta
import uuid

logger = logging.getLogger(__name__)

import json
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse, JsonResponse
from django.urls import reverse

def search(request):
    """
    AJAX Search for Subjects, Topics, and Blog Posts.
    """
    query = request.GET.get('q', '').strip()
    results = []
    
    if query and len(query) > 1:
        from django.db.models import Q
        
        # 1. Search Subjects (Normal & Formula)
        subjects = Subject.objects.filter(
            Q(title__icontains=query) | Q(description__icontains=query),
            is_private=False # Public only for simplicity in search, or check user access
        ).distinct()[:3]
        
        for sub in subjects:
            results.append({
                "type": "Formula" if sub.is_formula_collection else "Subject",
                "title": sub.title,
                "url": "#", # Landing page handles subjects via preview, but we can't deep link easily without ID. 
                            # Ideally we link to a subject page. For now, we can trigger the preview if on landing?
                            # Or just link to nothing/anchor?
                            # Actually, we don't have a dedicated page for subjects yet other than landing preview.
                            # Let's assume we can trigger preview via JS if we return ID/Title.
                            # Or better: "Review Files" or "Flashcards Hub" link?
                            # Let's link to the first folder/topic if possible?
                            # For now let's just use a placeholder or handle in JS.
                "action": "preview",
                "meta": sub.description,
                "id": sub.id
            })

        # 2. Search Topics (Flashcards)
        topics = Topic.objects.filter(
            Q(title__icontains=query),
            is_active=True,
            is_private=False
        ).select_related('subject').distinct()[:5]
        
        for t in topics:
            results.append({
                "type": "Flashcard",
                "title": t.title,
                "url": reverse('review:flashcards', args=[t.slug]),
                "meta": t.subject.title if t.subject else ""
            })

        # 3. Search Blog Posts
        posts = BlogPost.objects.filter(
            Q(title__icontains=query) | Q(summary__icontains=query),
            is_published=True
        ).distinct()[:3]
        
        for p in posts:
            results.append({
                "type": "Blog",
                "title": p.title,
                "url": p.get_absolute_url(),
                "meta": p.summary[:50] + "..."
            })
            
    return JsonResponse({"results": results})

def landing(request):
    """
    Marketing landing page (Spotify-style).
    """
    try:
        # Privacy Filter:
        # Show subject if:
        # 1. It is PUBLIC (is_private=False)
        # 2. OR User is in allowed_users
        
        # Note: allowed_users is M2M.
        # Logic: Q(is_private=False) | Q(allowed_users=request.user)
        # Anonymous users can only see is_private=False
        
        base_query = Subject.objects.all()
        
        if request.user.is_authenticated:
            # Complex query for logged-in users
            from django.db.models import Q
            subjects = base_query.filter(
                Q(is_formula_collection=False) & 
                (Q(is_private=False) | Q(allowed_users=request.user))
            ).distinct().order_by("order")
            
            # Fetch formula collections for the new section
            formula_subjects = base_query.filter(
                Q(is_formula_collection=True) & 
                (Q(is_private=False) | Q(allowed_users=request.user))
            ).distinct().order_by("order")
        else:
            # Anonymous users: Public only
            subjects = base_query.filter(is_private=False, is_formula_collection=False).order_by("order")
            formula_subjects = base_query.filter(is_private=False, is_formula_collection=True).order_by("order")
        
        # Build a simple dict for the preview pane: Subject Title -> List of Folders
        # This avoids extra AJAX calls for the landing page experience
        preview_data = {}
        itemlist_elements = []
        position_counter = 1
        
        # Helper to process a list of subjects and add to preview_data
        all_display_subjects = list(subjects) + list(formula_subjects)
        
        for sub in all_display_subjects:
            # Build visible topics queryset
            topics_query = sub.topics.filter(is_active=True)
            if request.user.is_authenticated:
                from django.db.models import Q
                topics_query = topics_query.filter(
                     Q(is_private=False) | Q(allowed_users=request.user)
                ).distinct()
            else:
                topics_query = topics_query.filter(is_private=False)

            folder_list = []
            # Prefer Folder model if available
            folders_qs = Folder.objects.filter(subject=sub).order_by("order", "title")
            if folders_qs.exists():
                for folder in folders_qs:
                    t_count = topics_query.filter(folder_ref=folder).count()
                    if t_count == 0:
                        continue
                    url = reverse("review:folder_topics", args=[sub.slug, folder.title])
                    folder_list.append({
                        "title": folder.title,
                        "count": t_count,
                        "url": url,
                        "slug": folder.title,
                    })

            # If no folders found via Folder model (or Folder model exists but no topics linked),
            # fall back to legacy string-based folder values
            if not folder_list:
                for f_name in topics_query.values_list("folder", flat=True).distinct():
                    display_name = f_name or "General"
                    t_count = topics_query.filter(folder=f_name).count()
                    if t_count == 0:
                        continue
                    url = reverse("review:folder_topics", args=[sub.slug, display_name])
                    folder_list.append({
                        "title": display_name,
                        "count": t_count,
                        "url": url,
                        "slug": display_name,
                    })

            preview_data[sub.title] = folder_list

            # Build ItemList elements (absolute URLs) - strictly we should list topics, but listing folders is okay for hierarchy
            # Or we can just list the subject URL?
            # Let's skip detailed ItemList for folders to keep it simple, or link to folder URLs.
            for f in folder_list:
                try:
                    full_url = request.build_absolute_uri(f["url"])
                    itemlist_elements.append({
                        "@type": "ListItem",
                        "position": position_counter,
                        "url": full_url
                    })
                    position_counter += 1
                except Exception:
                    pass
            
    except Exception as e:
        logger.error("Error in landing view: %s", e, exc_info=True)
        subjects = []
        formula_subjects = []
        preview_data = {}
    
    # Build ItemList JSON-LD
    jsonld_itemlist = ""
    try:
        if itemlist_elements:
            jsonld_itemlist = json.dumps({
                "@context": "https://schema.org",
                "@type": "ItemList",
                "itemListElement": itemlist_elements
            })
    except Exception:
        jsonld_itemlist = ""
    
    # Fetch blog posts for landing page
    blog_posts = BlogPost.objects.filter(is_published=True).order_by("-published_at")[:6]

    context = {
        "subjects": subjects,
        "formula_subjects": formula_subjects,
        "preview_data": preview_data,
        "jsonld_itemlist": jsonld_itemlist,
        "blog_posts": blog_posts
    }
    
    return render(request, "review/landing.html", context)

def pricing(request):
    """
    Pricing page with comparison table.
    Env-var driven pricing values.
    """
    context = {
        "price_monthly_premium": os.getenv("PRICE_MONTHLY_PREMIUM", "100"),
        "price_yearly_premium": os.getenv("PRICE_YEARLY_PREMIUM", "600"),
        "price_monthly_free": os.getenv ("PRICE_FREE_PREMIUM", "0"),
        "currency_symbol": os.getenv("CURRENCY_SYMBOL", "₱"),
        "is_premium": UserAccess.user_has_valid_access(request.user),
    }
    return render(request, "review/pricing.html", context)

def flashcards(request, topic_slug=None, *args, **kwargs):
    """
    Render flashcards page.
    Spec: /flashcards/<topic_slug>/
    """
    # normalize incoming identifier
    incoming = topic_slug or kwargs.get("topic_slug")

    if not incoming:
        logger.warning("flashcards view called without topic identifier; returning 404")
        return render(request, "review/error.html", {"message": "Topic not specified."}, status=404)

    # attempt to resolve topic: always use slug
    topic = None
    try:
        topic = Topic.objects.filter(slug=incoming).first()
        if not topic:
             return render(request, "review/error.html", {"message": "Topic not found."}, status=404)
    except Exception as e:
        logger.exception("Failed to resolve topic '%s': %s", incoming, e)
        return render(request, "review/error.html", {"message": "An error occurred."}, status=404)

    # Build SEO questions listing
    try:
        # Use the same deterministic ordering as the flashcards API
        questions_qs = topic.questions.filter(is_active=True).order_by("order", "id")
        seo_questions = []
        idx = 1
        for q in questions_qs:
            ans_text = ""
            q_ans = str(q.answer).strip() if q.answer is not None else ""
            if q.choices:
                for c in q.choices:
                    c_key = str(c.get("key", "")).strip()
                    c_text = str(c.get("text", "")).strip()
                    if c_key == q_ans or c_text == q_ans:
                        ans_text = c.get("text", "")
                        break
            if not ans_text:
                ans_text = q.answer or ""
            seo_questions.append({
                "index": idx,
                "prompt": getattr(q, "prompt", ""),
                "answer_text": ans_text
            })
            idx += 1
        topic_questions_count = questions_qs.count()
    except Exception:
        seo_questions = []
        topic_questions_count = 0
    seo_intro = f"This topic is focused on {topic.title}. These flashcards cover key concepts and exam-style questions to help you prepare effectively."
    topic_seo_text = (getattr(topic, "description", "") or "").strip() or seo_intro
    try:
        suggested = []
        if getattr(topic, "subject", None):
            tq = topic.subject.topics.filter(is_active=True).exclude(id=topic.id)
            if request.user.is_authenticated:
                from django.db.models import Q
                tq = tq.filter(Q(is_private=False) | Q(allowed_users=request.user)).distinct()
            else:
                tq = tq.filter(is_private=False)
            for t in tq.order_by("order")[:5]:
                suggested.append({"title": t.title, "slug": t.slug})
    except Exception:
        suggested = []

    context = {
        "topic_slug": topic.slug,
        "topic_title": getattr(topic, "title", str(topic)),
        "subject_slug": topic.subject.slug if getattr(topic, "subject", None) else "",
        "is_premium_user": UserAccess.user_has_valid_access(request.user),
        "feature_random_enabled": is_feature_enabled("RANDOM_FLASHCARDS_ENABLED"),
        "page_size_default": 50,
        "seo_questions": seo_questions,
        "topic_questions_count": topic_questions_count,
        "seo_intro": seo_intro,
        "topic_seo_text": topic_seo_text,
        "suggested_topics": suggested,
    }
    return render(request, "review/flashcards.html", context)

def flashcards_hub(request):
    """
    Indexable hub listing public subjects and topics with links to flashcards.
    """
    try:
        base_query = Subject.objects.all()
        if request.user.is_authenticated:
            from django.db.models import Q
            subjects = base_query.filter(
                Q(is_private=False) | Q(allowed_users=request.user)
            ).distinct().order_by("order")
        else:
            subjects = base_query.filter(is_private=False).order_by("order")
        # Build subject -> topics
        subject_topics = []
        for sub in subjects:
            tq = sub.topics.filter(is_active=True)
            if request.user.is_authenticated:
                from django.db.models import Q
                tq = tq.filter(Q(is_private=False) | Q(allowed_users=request.user)).distinct()
            else:
                tq = tq.filter(is_private=False)
            topics = tq.order_by("order")
            subject_topics.append({"subject": sub, "topics": topics})
    except Exception:
        subject_topics = []
    context = {
        "subject_topics": subject_topics
    }
    return render(request, "review/flashcards_hub.html", context)

def review_files(request):
    """
    List downloadable review files.
    """
    # Redirect non-logged in users to pricing (or login) to prevent bypassing
    if not request.user.is_authenticated:
        return redirect("review:pricing")

    # Fetch all files, but we might hide premium ones or show them locked in template
    files = ReviewFile.objects.all().order_by("-created_at")
    is_premium = UserAccess.user_has_valid_access(request.user)
    
    # Optional: If you want to strictly gate files to premium ONLY:
    # if not is_premium:
    #     return redirect("review:pricing")
    
    context = {
        "files": files,
        "is_premium": is_premium,
    }
    return render(request, "review/review_files.html", context)


def mock_exams(request):
    """
    List available mock exams.
    Now filters Private exams.
    """
    # Redirect non-logged in users to pricing to prevent bypassing
    if not request.user.is_authenticated:
        return redirect("review:pricing")

    base_qs = MockExam.objects.all().order_by("-created_at")
    
    # Filter Privacy
    if request.user.is_authenticated:
        from django.db.models import Q
        # Fix: Filter mock exams correctly
        # Exams are visible if:
        # 1. allowed_users contains the current user (Explicit assignment)
        # 2. OR (is_private=False AND allowed_users is empty) 
        #    (This ensures that if users are assigned, it implicitly becomes private/exclusive to them, 
        #     preventing accidental leaks if 'is_private' was forgotten)
        exams = base_qs.filter(
            Q(allowed_users=request.user) | 
            (Q(is_private=False) & Q(allowed_users__isnull=True))
        ).distinct()
    else:
        # Should not be reached due to redirect above, but good fallback
        exams = base_qs.filter(is_private=False)
        
    is_premium = UserAccess.user_has_valid_access(request.user)
    
    context = {
        "exams": exams,
        "is_premium": is_premium,
    }
    return render(request, "review/mock_exams.html", context)


def take_mock_exam(request, exam_id):
    """
    Render the exam interface or handle submission.
    """
    if not request.user.is_authenticated:
        return redirect("review:login") # Assuming login url name

    exam = get_object_or_404(MockExam, id=exam_id)
    
    # Check access using the robust model method
    if not exam.is_available_for(request.user):
        # Determine specific error for clarity
        if exam.is_premium and not UserAccess.user_has_valid_access(request.user):
            msg = "This mock exam requires premium access."
        elif exam.is_private and not exam.allowed_users.filter(id=request.user.id).exists():
            msg = "You do not have permission to access this private exam."
        else:
            msg = "Access denied."
            
        return render(request, "review/error.html", {"message": msg})

    # Find active session or create new
    now = timezone.now()
    session = ExamSession.objects.filter(
        user=request.user, 
        mock_exam=exam, 
        state=ExamSession.STATE_RUNNING
    ).first()

    if session and session.expires_at < now:
        # Expired, finalize it
        session.finalize(auto_timed_out=True)
        return redirect("review:exam_result", session_id=session.id)

    if request.method == "POST":
        # Handle submission
        if not session:
             # Should not happen in normal flow, but defensive
             return redirect("review:mock_exams")
        
        # Parse answers from POST
        # Expected format: answer_questionID = choice_key
        answers = {}
        for key, value in request.POST.items():
            if key.startswith("answer_"):
                q_id = key.split("_")[1]
                answers[q_id] = value
        
        session.answers = answers
        session.finalize(auto_timed_out=False)
        return redirect("review:exam_result", session_id=session.id)

    if not session:
        # Create new session
        duration = exam.duration_minutes
        expires_at = now + timedelta(minutes=duration)
        session = ExamSession.objects.create(
            user=request.user,
            mock_exam=exam,
            expires_at=expires_at,
            state=ExamSession.STATE_RUNNING,
            answers={}
        )

    # Calculate remaining time
    remaining_seconds = max(0, (session.expires_at - now).total_seconds())

    # Get questions
    questions = exam.questions.filter(is_active=True).order_by("order")
    # If using random pool, logic would be different (need to store selected Qs in session)
    # Assuming exam has fixed questions for now as per "1 continuous page" standard
    
    context = {
        "exam": exam,
        "session": session,
        "questions": questions,
        "remaining_seconds": int(remaining_seconds),
    }
    return render(request, "review/take_mock_exam.html", context)


def exam_result(request, session_id):
    """
    Show exam results.
    """
    session = get_object_or_404(ExamSession, id=session_id, user=request.user)
    
    # Calculate score if not already done (idempotent in finalize, but let's double check)
    if session.state == ExamSession.STATE_RUNNING:
        session.finalize()
    
    # Re-fetch questions to show correct/incorrect
    # Note: If questions changed since exam, this might be slightly off. 
    # For a robust system, we'd store question snapshots. For "simple", we fetch live.
    questions = session.mock_exam.questions.all().order_by("order")
    
    # Build detailed result list
    results = []
    correct_count = 0
    total_count = 0
    
    user_answers = session.answers or {}
    
    for q in questions:
        total_count += 1
        user_ans = user_answers.get(str(q.id))
        
        # Determine if correct
        # Logic depends on Question type. Assuming MC (JSON choices) for now.
        # Question.answer stores the correct key for MC? Or the text?
        # Model doc says: choices=[{"key":"A", "text":"..."}], answer="text" (or key?)
        # Usually answer field stores the correct key for MC.
        
        is_correct = False
        correct_answer_text = ""
        
        # Normalize inputs
        # Handle None user_ans
        user_ans_str = str(user_ans).strip() if user_ans is not None else ""
        q_answer_str = str(q.answer).strip() if q.answer is not None else ""
        
        # Find correct answer text from choices
        if q.choices:
            for c in q.choices:
                c_key_str = str(c.get("key", "")).strip()
                c_text_str = str(c.get("text", "")).strip()
                
                # Check if this choice is the correct one
                if c_key_str == q_answer_str:
                    correct_answer_text = c.get("text")
                elif c_text_str == q_answer_str: # Fallback
                     correct_answer_text = c.get("text")
        
        if not correct_answer_text:
             correct_answer_text = q.answer # Fallback for text questions
        
        # Check correctness
        # Use simple string compare of keys
        if user_ans_str and user_ans_str == q_answer_str:
            is_correct = True
            correct_count += 1
            
        # Get user answer text
        user_answer_text = user_ans
        # Ensure we pass keys to template for comparison logic
        # user_ans is the key (e.g. "A"), q.answer is the key (e.g. "A")
        
        # FIX: The template logic uses 'choice_key == question_answer'. 
        # We need to make sure we are passing the KEY as question_answer in the context if it's not on the object.
        # But wait, q.answer IS the key.
        
        # We need to pass the raw key values to the template context item to ensure 
        # the template doesn't have to guess or use the model field directly if it's modified.
        
        results.append({
            "question": q,
            "user_answer": user_ans_str, # Pass normalized string key
            "is_correct": is_correct,
            "correct_answer_text": correct_answer_text,
            "user_answer_text": user_answer_text,
            "question_answer_key": q_answer_str # Explicitly pass the correct key
        })
        
    # Update score if needed (simple calc)
    # Important: Update session.score in context immediately, even if save() is deferred or cached
    if total_count > 0:
        calculated_score = (correct_count / total_count) * 100
        session.score = calculated_score # Update object in memory for template
        
        # Save to DB
        # Use update() to bypass potential race conditions or signal issues if needed, but save() is standard
        # Check if we need to save (avoid redundant writes if already set)
        # But since we just recalculated based on strict logic, let's enforce it.
        session.save(update_fields=["score"])
    
    # Prepare context for template
    percentage = float(session.score or 0.0)
    context = {
        "percentage": percentage,
        "correct_count": correct_count,
        "total_count": total_count,
        "results": results,
    }
    return render(request, "review/exam_result.html", context)
from django.contrib.auth.decorators import login_required

from .forms import PaymentUploadForm

from django_ratelimit.decorators import ratelimit

@ratelimit(key='ip', rate='5/m', block=True)
def upload_payment(request):
    """
    Handle manual payment receipt upload using strict Form validation.
    Accessible to anyone (no login required).
    """
    if request.method == "POST":
        form = PaymentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # Create transaction but don't save to DB yet (need to set fields not in form)
            transaction = form.save(commit=False)
            
            # Associate user if logged in
            transaction.user = request.user if request.user.is_authenticated else None
            
            # Metadata from extra fields
            transaction.metadata = {
                "full_name": form.cleaned_data.get("full_name"),
                "email": form.cleaned_data.get("email"),
                "desired_username": form.cleaned_data.get("desired_username")
            }
            transaction.status = PaymentTransaction.STATUS_PENDING
            transaction.save()
            
            return render(request, "review/payment_success.html")
    else:
        # Pre-fill email if logged in
        initial = {}
        if request.user.is_authenticated:
            initial['email'] = request.user.email
        form = PaymentUploadForm(initial=initial)

    return render(request, "review/payment_upload.html", {"form": form})

def info_page(request):
    return render(request, "review/info.html")

def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /pricing/upload/",
        f"Sitemap: {request.scheme}://{request.get_host}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")

def sitemap_xml(request):
    base = f"{request.scheme}://{request.get_host}"
    urls = [
        {"loc": f"{base}/", "priority": "0.9"},
        {"loc": f"{base}/pricing/", "priority": "0.8"},
        {"loc": f"{base}/info/", "priority": "0.6"},
        {"loc": f"{base}/blog/", "priority": "0.8"},
    ]
    
    # Add blog posts
    for post in BlogPost.objects.filter(is_published=True):
        urls.append({
            "loc": f"{base}{post.get_absolute_url()}",
            "priority": "0.7"
        })

    xml_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for u in urls:
        xml_parts.append("<url>")
        xml_parts.append(f"<loc>{u['loc']}</loc>")
        xml_parts.append(f"<priority>{u['priority']}</priority>")
        xml_parts.append("</url>")
    xml_parts.append("</urlset>")
    return HttpResponse("\n".join(xml_parts), content_type="application/xml")
