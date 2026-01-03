# review/admin.py
from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import path
from django.shortcuts import render, redirect
from django.utils.html import format_html
from django import forms
from django.conf import settings
from django.db import transaction

from .models import (
    Subject, Topic, Question, FeatureFlag, UserAccess,
    PaymentTransaction, ReviewFile, MockExam, UserAnalytics, DailyQuestion, ExamSession,
    Folder,
    is_feature_enabled,
)

# -------------------------
# Helper admin utilities
# -------------------------
def file_link(obj):
    if not obj or not getattr(obj, "file", None):
        return "-"
    url = obj.file.url
    return format_html('<a href="{}" target="_blank">Download</a>', url)
file_link.short_description = "File"


# -------------------------
# FeatureFlag admin
# -------------------------
@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ("key", "enabled", "description", "updated_at")
    search_fields = ("key",)
    list_editable = ("enabled",)


# -------------------------
# Subject / Topic / Question admins
# -------------------------
@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "order", "is_private", "is_formula_collection", "created_at")
    list_filter = ("is_private", "is_formula_collection")
    search_fields = ("title", "slug")
    ordering = ("order", "title")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("allowed_users",)  # Easier multi-select for users
    fields = ("title", "slug", "description", "image", "order", "is_private", "is_formula_collection", "allowed_users")

    change_list_template = "review/admin/subject_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("import-csv/", self.admin_site.admin_view(self.import_csv_view), name="review_subject_import_csv"),
            path("import-flashcards/", self.admin_site.admin_view(self.import_flashcards_view), name="review_subject_import_flashcards"),
        ]
        return custom + urls

    def import_csv_view(self, request):
        # Gate through feature flag
        if not is_feature_enabled("IMPORTS_ENABLED"):
            self.message_user(request, "CSV imports are disabled (FEATURE_IMPORTS_ENABLED is OFF).", level=messages.WARNING)
            return redirect("..")

        # Only staff can use admin pages; admin_site.admin_view already enforces that
        if request.method == "POST" and request.FILES.get("csv_file"):
            csv_file = request.FILES["csv_file"]
            dry_run = request.POST.get("dry_run", "on") == "on"
            # Save uploaded file to MEDIA for audit; small files ok
            from django.core.files.storage import default_storage
            save_path = default_storage.save(f"imports/{csv_file.name}", csv_file)
            # Use management command logic for parsing/validation
            # Importer expects filesystem path; we can open storage file
            full_path = default_storage.path(save_path) if hasattr(default_storage, "path") else default_storage.open(save_path).name
            # call importer logic from management command module for reuse
            from importlib import import_module
            importer = import_module("review.management.commands.import_csv")
            cmd = importer.Command()
            try:
                result = cmd.handle_import_file(full_path, commit=not dry_run, user=request.user)
            except Exception as exc:
                self.message_user(request, f"Import failed: {exc}", level=messages.ERROR)
                context = {"error": str(exc)}
                return render(request, "review/admin/import_upload.html", context)
            # Show preview/summary
            context = {
                "preview": result.get("preview", []),
                "summary": result.get("summary", {}),
                "dry_run": dry_run,
                "csv_name": csv_file.name,
                "commit_done": not dry_run and result.get("created", 0) > 0,
            }
            # If dry_run, show confirm button to commit (POST back with commit)
            return render(request, "review/admin/import_preview.html", context)
        # GET shows upload form
        return render(request, "review/admin/import_upload.html", {})
    
    def import_flashcards_view(self, request):
        """
        Admin-only UI for pasting Q/A flashcards in the compact format.
        Now supports selecting Subject/Topic via dropdowns as defaults.
        """

        # Feature flag gate
        if not is_feature_enabled("IMPORTS_ENABLED"):
            self.message_user(
                request,
                "Flashcard imports are disabled (IMPORTS_ENABLED is OFF).",
                level=messages.WARNING
            )
            return redirect("..")
    
        # Import the CLI command class (re-usable)
        try:
            from review.management.commands.import_paste import Command as FlashImportCmd
        except Exception as exc:
            self.message_user(
                request,
                f"Import command not available: {exc}",
                level=messages.ERROR
            )
            return redirect("..")
        
        cmd = FlashImportCmd()

        # Context for dropdowns
        subjects = Subject.objects.all().order_by("order", "title")
        topics = Topic.objects.filter(is_active=True).select_related("subject").order_by("subject__order", "order")

        if request.method == "POST":
            paste_text = request.POST.get("paste_text", "")
            commit = request.POST.get("commit", "") == "1"
            
            # Get selected defaults
            subject_id = request.POST.get("subject_id")
            topic_id = request.POST.get("topic_id")
            
            default_subject = Subject.objects.filter(id=subject_id).first() if subject_id else None
            default_topic = Topic.objects.filter(id=topic_id).first() if topic_id else None

            # Parse using command logic (dry-run)
            try:
                blocks, errors = cmd.parse_blocks(
                    paste_text,
                    default_subject=default_subject,
                    default_topic=default_topic
                )
            except Exception as exc:
                self.message_user(request, f"Failed to parse input: {exc}", level=messages.ERROR)
                return render(request, "review/admin/flashcard_upload.html", {
                    "error": str(exc),
                    "subjects": subjects,
                    "topics": topics,
                    "paste_text": paste_text
                })
            
            # Dry-run preview
            if not commit:
                context = {
                    "parsed": blocks,
                    "errors": errors,
                    "commit_mode": False,
                    "preview_limit": 50,
                    "original_paste": paste_text,
                    "subject_id": subject_id,
                    "topic_id": topic_id,
                }
                return render(request, "review/admin/flashcard_preview.html", context)
            
            # Commit mode
            # We need to re-parse or trust the input.
            # Ideally we pass the parsed objects to commit, but cmd._commit_blocks logic is in handle() usually.
            # import_paste.py's handle() does parsing then committing.
            # We need to adapt import_paste.py to expose a commit method or duplicate logic.
            # import_paste.py logic:
            
            try:
                # We reuse the logic from the command. 
                # Since we already parsed, we can iterate and save.
                # But import_paste.py doesn't expose a standalone commit function easily accessible without copy-paste logic?
                # Actually, let's look at import_paste.py again. handle() does it all.
                # We can implement a helper in the command class or just write the save logic here.
                # Writing it here is safer/clearer for now to ensure we use the defaults.
                
                # ... Wait, import_paste.py logic for saving is:
                # 1. Map subjects/topics
                # 2. Bulk create
                
                # Let's extract that logic or replicate it. Replicating is fine for now as it's simple Django ORM.
                
                created_count = 0
                batch_size = 1000
                to_create = []
                
                # Cache lookup
                subj_cache = {s.slug: s for s in Subject.objects.all()}
                topic_cache = {} # (subj_slug, topic_slug) -> Topic
                
                for p in blocks:
                    # Resolve Subject
                    subj = subj_cache.get(p.subject_slug)
                    if not subj:
                        subj = Subject.objects.create(slug=p.subject_slug, title=p.subject_title, order=0)
                        subj_cache[subj.slug] = subj
                    
                    # Resolve Topic
                    t_key = (subj.slug, p.topic_slug)
                    topic = topic_cache.get(t_key)
                    if not topic:
                        topic = Topic.objects.filter(subject=subj, slug=p.topic_slug).first()
                        if not topic:
                            topic = Topic.objects.create(subject=subj, slug=p.topic_slug, title=p.topic_title, order=0)
                        topic_cache[t_key] = topic

                    # Create Question
                    q = Question(
                        topic=topic,
                        order=p.order or 0,
                        prompt=p.prompt,
                        choices=p.choices or None,
                        answer=(p.answer_key or "") if not p.choices else (p.answer_key or ""),
                        answer_type=(Question.ANSWER_MC if p.choices else Question.ANSWER_TEXT),
                        is_active=True,
                        is_premium=p.is_premium
                    )
                    to_create.append(q)
                    
                    if len(to_create) >= batch_size:
                        Question.objects.bulk_create(to_create)
                        created_count += len(to_create)
                        to_create = []
                
                if to_create:
                    Question.objects.bulk_create(to_create)
                    created_count += len(to_create)

            except Exception as exc:
                self.message_user(request, f"Import failed during commit: {exc}", level=messages.ERROR)
                return render(request, "review/admin/flashcard_preview.html", {"parsed": blocks, "errors": [str(exc)], "original_paste": paste_text})

            self.message_user(request, f"Imported {created_count} flashcards.", level=messages.SUCCESS)
            return redirect("..")

        # GET — show paste screen
        return render(request, "review/admin/flashcard_upload.html", {
            "subjects": subjects,
            "topics": topics
        })

class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    fields = ("prompt", "answer", "order", "is_active", "is_premium")
    show_change_link = True

@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ("title", "subject", "order")
    list_filter = ("subject",)
    search_fields = ("title", "subject__title")
    list_editable = ("order",)
    ordering = ("subject", "order")

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("title", "subject", "folder_ref", "order", "is_active", "is_private", "question_count")
    list_filter = ("subject", "folder_ref", "is_active", "is_private")
    search_fields = ("title", "subject__title", "folder_ref__title")
    # Enable quick editing of folder and order
    list_editable = ("folder_ref", "order", "is_active")
    ordering = ("subject", "folder_ref__order", "folder_ref__title", "order")
    prepopulated_fields = {"slug": ("title",)}  # Auto-fill slug from title
    filter_horizontal = ("allowed_users",)

    def question_count(self, obj):
        return obj.questions.count()
    question_count.short_description = "Questions"


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("short_prompt", "subject_name", "topic", "order", "is_active", "is_premium")
    list_filter = ("topic__subject", "topic", "is_active", "is_premium", "answer_type")
    search_fields = ("prompt", "answer", "explanation", "topic__title")
    ordering = ("topic__subject", "topic", "order")
    autocomplete_fields = ["topic"]
    # Enable quick editing of common fields
    list_editable = ("order", "is_active", "is_premium")

    def subject_name(self, obj):
        return obj.topic.subject.title
    subject_name.short_description = "Subject"
    subject_name.admin_order_field = "topic__subject"

    def short_prompt(self, obj):
        return (obj.prompt[:100] + "...") if len(obj.prompt or "") > 100 else obj.prompt
    short_prompt.short_description = "Prompt"


# -------------------------
# Other admins (simple)
# -------------------------
@admin.register(UserAccess)
class UserAccessAdmin(admin.ModelAdmin):
    list_display = ("user", "is_active", "expires_at", "plan", "source_reference")
    list_filter = ("is_active",)
    search_fields = ("user__username", "source_reference")


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "status", "created_at", "provider_reference")
    list_filter = ("status",)
    readonly_fields = ("uploaded_file_preview",)

    def uploaded_file_preview(self, obj):
        return file_link(obj)
    uploaded_file_preview.short_description = "Uploaded proof"


@admin.register(ReviewFile)
class ReviewFileAdmin(admin.ModelAdmin):
    list_display = ("title", "uploaded_by", "is_premium", "created_at", "file_link")
    list_filter = ("is_premium",)
    search_fields = ("title",)
    readonly_fields = ("file_link",)

    def file_link(self, obj):
        return file_link(obj)
    file_link.short_description = "File"


@admin.register(MockExam)
class MockExamAdmin(admin.ModelAdmin):
    list_display = ("title", "duration_minutes", "is_premium", "is_private", "created_at")
    list_filter = ("is_premium", "is_private")
    search_fields = ("title",)
    filter_horizontal = ("questions", "allowed_users")  # Added allowed_users here
    help_text = "Note: Private exams also require Premium if 'Is Premium' is checked."


@admin.register(UserAnalytics)
class UserAnalyticsAdmin(admin.ModelAdmin):
    list_display = ("user", "question", "topic", "total_attempts", "correct_count", "incorrect_count")


@admin.register(DailyQuestion)
class DailyQuestionAdmin(admin.ModelAdmin):
    list_display = ("date", "question", "is_active")


@admin.register(ExamSession)
class ExamSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "mock_exam", "state", "started_at", "expires_at", "finished_at")
    readonly_fields = ("answers", "metadata", "score")
