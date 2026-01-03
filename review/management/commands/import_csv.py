# review/management/commands/import_csv.py
import csv
import os
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.contrib.auth import get_user_model

from review.models import Subject, Topic, Question, is_feature_enabled

User = get_user_model()


class Command(BaseCommand):
    help = "Import Subjects, Topics, Questions from a CSV. Columns: subject_slug,subject_title,topic_slug,topic_title,question_order,prompt,choices_json,answer,answer_type,is_premium"

    def add_arguments(self, parser):
        parser.add_argument("--file", "-f", required=False, help="Path to CSV file (if omitted, interactive mode)")
        parser.add_argument("--dry-run", action="store_true", dest="dry_run", default=False, help="Parse and validate but do not write to DB")
        parser.add_argument("--commit", action="store_true", dest="commit", default=False, help="Commit changes to DB (opposite of dry-run)")
        parser.add_argument("--skip-existing", action="store_true", dest="skip_existing", default=False, help="Skip rows that match existing subject/topic/question")

    def handle(self, *args, **options):
        if not is_feature_enabled("IMPORTS_ENABLED"):
            raise CommandError("Imports feature is disabled (FEATURE_IMPORTS_ENABLED is OFF).")

        path = options.get("file")
        dry_run = options.get("dry_run") and not options.get("commit")
        commit = options.get("commit")
        skip_existing = options.get("skip_existing")

        if not path:
            raise CommandError("Please provide --file <path>")

        if not os.path.exists(path):
            raise CommandError(f"File not found: {path}")

        result = self.handle_import_file(path, commit=commit, user=None, skip_existing=skip_existing)
        self.stdout.write("Import summary:")
        for k, v in result.get("summary", {}).items():
            self.stdout.write(f" - {k}: {v}")
        if dry_run:
            self.stdout.write("Dry-run mode (no DB changes). Use --commit to apply changes.")

    def handle_import_file(self, path, commit=False, user: User = None, skip_existing=False):
        """
        Reusable import function:
        - parse CSV
        - validate rows
        - return preview and summary
        - if commit==True, create DB records in an atomic transaction
        """
        preview = []
        summary = {"rows": 0, "created_subjects": 0, "created_topics": 0, "created_questions": 0, "skipped": 0, "errors": 0}
        errors = []

        # Supported columns expected (extra columns are ignored)
        expected_cols = ["subject_slug", "subject_title", "topic_slug", "topic_title", "question_order", "prompt", "choices_json", "answer", "answer_type", "is_premium"]

        # Read CSV
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for rownum, row in enumerate(reader, start=1):
                summary["rows"] += 1
                # Basic validation
                subject_slug = (row.get("subject_slug") or "").strip()
                subject_title = (row.get("subject_title") or "").strip()
                topic_slug = (row.get("topic_slug") or "").strip()
                topic_title = (row.get("topic_title") or "").strip()
                prompt = (row.get("prompt") or "").strip()
                order = row.get("question_order") or "0"
                try:
                    order = int(order)
                except Exception:
                    order = 0

                if not subject_slug or not subject_title or not topic_slug or not topic_title or not prompt:
                    summary["errors"] += 1
                    errors.append({"row": rownum, "error": "Missing required field (subject/topic/prompt).", "row": row})
                    continue

                # check existence
                subj = Subject.objects.filter(slug=subject_slug).first()
                topic = None
                if subj:
                    topic = subj.topics.filter(slug=topic_slug).first()

                if skip_existing and subj and topic:
                    # optionally skip creation, but still add question
                    pass

                preview_entry = {
                    "row": rownum,
                    "subject_slug": subject_slug,
                    "subject_title": subject_title,
                    "topic_slug": topic_slug,
                    "topic_title": topic_title,
                    "prompt": prompt[:200],
                    "order": order,
                }
                preview.append(preview_entry)

        # If commit is False, return preview/summary
        if not commit:
            return {"preview": preview[:200], "summary": summary, "errors": errors}

        # commit: perform DB writes in a transaction
        try:
            with transaction.atomic():
                with open(path, newline="", encoding="utf-8") as fh:
                    reader = csv.DictReader(fh)
                    for rownum, row in enumerate(reader, start=1):
                        subject_slug = (row.get("subject_slug") or "").strip()
                        subject_title = (row.get("subject_title") or "").strip()
                        topic_slug = (row.get("topic_slug") or "").strip()
                        topic_title = (row.get("topic_title") or "").strip()
                        prompt = (row.get("prompt") or "").strip()
                        order = row.get("question_order") or "0"
                        try:
                            order = int(order)
                        except Exception:
                            order = 0
                        is_premium = str(row.get("is_premium", "")).strip().lower() in ("1", "true", "yes", "on")
                        choices_json = row.get("choices_json") or None
                        answer = row.get("answer") or None
                        answer_type = row.get("answer_type") or None

                        # Subject
                        subj, created_s = Subject.objects.get_or_create(slug=subject_slug, defaults={"title": subject_title})
                        if created_s:
                            summary["created_subjects"] += 1

                        # Topic
                        topic, created_t = Topic.objects.get_or_create(subject=subj, slug=topic_slug, defaults={"title": topic_title})
                        if created_t:
                            summary["created_topics"] += 1

                        # Question uniqueness: use topic + order + prompt for idempotency
                        q_filters = {"topic": topic, "prompt": prompt}
                        if skip_existing and Question.objects.filter(**q_filters).exists():
                            summary["skipped"] += 1
                            continue

                        q = Question.objects.create(
                            topic=topic,
                            order=order,
                            prompt=prompt,
                            choices=choices_json if choices_json else None,
                            answer=answer,
                            answer_type=answer_type or Question.ANSWER_TEXT,
                            is_active=True,
                            is_premium=is_premium,
                        )
                        summary["created_questions"] += 1
        except IntegrityError as exc:
            raise

        return {"preview": preview[:200], "summary": summary, "errors": errors, "created": summary["created_questions"]}

