# review/management/commands/import_paste.py
import re
import json
import hashlib
import math
from typing import List, Dict, Any, Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from review.models import Subject, Topic, Question, is_feature_enabled

# Regexes for block parsing (compact MC format)
RE_Q = re.compile(r"^\s*Q:\s*(.+)", re.IGNORECASE)
RE_CHOICE = re.compile(r"^\s*([A-Z])\)\s*(.+)")
RE_ANSWER = re.compile(r"^\s*Answer:\s*(.+)", re.IGNORECASE)
RE_SUBJECT = re.compile(r"^\s*Subject:\s*(.+)", re.IGNORECASE)
RE_TOPIC = re.compile(r"^\s*Topic:\s*(.+)", re.IGNORECASE)
RE_ORDER = re.compile(r"^\s*Order:\s*(\d+)", re.IGNORECASE)
SEPARATOR = re.compile(r"^\s*[-]{3,}\s*$")  # lines with --- separate questions

BATCH_SIZE_DEFAULT = 1000


def _normalize_slug(s: str):
    return re.sub(r"[^a-z0-9\-]+", "-", s.strip().lower()).strip("-")


def _hash_record(subject_slug, topic_slug, prompt):
    key = f"{subject_slug}|{topic_slug}|{prompt[:250]}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


class ParsedQuestion:
    def __init__(self, prompt: str, choices: Optional[List[Dict[str, str]]],
                 answer_key: Optional[str], subject_slug: str, subject_title: str,
                 topic_slug: str, topic_title: str, order: int, is_premium: bool = False,
                 raw_block: str = ""):
        self.prompt = prompt
        self.choices = choices or []
        self.answer_key = answer_key
        self.subject_slug = subject_slug
        self.subject_title = subject_title
        self.topic_slug = topic_slug
        self.topic_title = topic_title
        self.order = order
        self.is_premium = is_premium
        self.raw_block = raw_block
        self.hash = _hash_record(self.subject_slug, self.topic_slug, self.prompt)


class Command(BaseCommand):
    help = "Import questions by pasting a text file (compact block format) or CSV. Supports dry-run & batch commits."

    def add_arguments(self, parser):
        parser.add_argument("--file", "-f", required=False, help="Path to text file to import (if omitted, reads from stdin).")
        parser.add_argument("--commit", action="store_true", help="Commit to DB. Without --commit, runs as dry-run preview.")
        parser.add_argument("--batch-size", type=int, default=BATCH_SIZE_DEFAULT, help="Batch size for bulk_create (default 1000).")
        parser.add_argument("--skip-existing", action="store_true", help="Skip creating questions that appear to already exist.")

    def handle(self, *args, **options):
        if not is_feature_enabled("IMPORTS_ENABLED"):
            raise CommandError("Imports feature disabled (FEATURE_IMPORTS_ENABLED is OFF).")

        path = options.get("file")
        commit = options.get("commit", False)
        batch_size = options.get("batch_size") or BATCH_SIZE_DEFAULT
        skip_existing = options.get("skip_existing", False)

        if path:
            with open(path, "r", encoding="utf-8") as fh:
                raw = fh.read()
        else:
            self.stdout.write("Paste input now (end with EOF / Ctrl+Z on Windows):")
            raw = ""
            try:
                while True:
                    line = input()
                    raw += line + "\n"
            except EOFError:
                pass

        parsed, errors = self.parse_blocks(raw)
        self.stdout.write(f"Parsed {len(parsed)} question blocks; errors: {len(errors)}")
        if errors:
            for e in errors[:20]:
                self.stdout.write(f"ERR: {e}")
        # Show a short preview
        preview_count = min(20, len(parsed))
        self.stdout.write("Preview of first %d items:" % preview_count)
        for i, p in enumerate(parsed[:preview_count], start=1):
            self.stdout.write(f"{i}. Subject={p.subject_title} ({p.subject_slug}) Topic={p.topic_title} ({p.topic_slug}) Order={p.order}")
            self.stdout.write(f"   Prompt: {p.prompt[:200]}")
            if p.choices:
                self.stdout.write("   Choices: " + ", ".join([f"{c['key']}:{c['text'][:40]}" for c in p.choices]))
            self.stdout.write(f"   AnswerKey: {p.answer_key}")
        if not commit:
            self.stdout.write("Dry-run mode (no DB writes). Use --commit to apply changes.")
            return

        # commit; create subjects, topics, questions in batches
        created_questions = 0
        total = len(parsed)
        # To speed up, map existing subjects/topics
        subj_cache = {s.slug: s for s in Subject.objects.all()}
        topic_cache = {}

        to_create = []
        for p in parsed:
            subj = subj_cache.get(p.subject_slug)
            if not subj:
                subj = Subject(slug=p.subject_slug, title=p.subject_title or p.subject_slug, order=0)
                subj.save()
                subj_cache[subj.slug] = subj
            t_key = (subj.slug, p.topic_slug)
            topic = topic_cache.get(t_key)
            if not topic:
                topic = subj.topics.filter(slug=p.topic_slug).first()
                if not topic:
                    topic = Topic.objects.create(subject=subj, slug=p.topic_slug, title=p.topic_title or p.topic_slug, order=0)
                topic_cache[t_key] = topic

            # skip existing
            if skip_existing and Question.objects.filter(topic=topic, prompt=p.prompt).exists():
                continue

            # prepare question object (do not save yet)
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
                created_questions += len(to_create)
                to_create = []
                self.stdout.write(f"Committed {created_questions}/{total} questions...")
        # flush remaining
        if to_create:
            Question.objects.bulk_create(to_create)
            created_questions += len(to_create)
        self.stdout.write(f"Import complete. Created questions: {created_questions}")
    # ---------- parsing ----------
    def parse_blocks(self, raw: str, default_subject=None, default_topic=None):
        """
        Parse raw text into ParsedQuestion objects.
        Accepts the compact MC format described in docs.
        """
        lines = raw.splitlines()
        blocks = []
        cur = []
        for ln in lines:
            if SEPARATOR.match(ln):
                if cur:
                    blocks.append("\n".join(cur).strip())
                    cur = []
            else:
                cur.append(ln)
        if cur and any(l.strip() for l in cur):
            blocks.append("\n".join(cur).strip())

        parsed = []
        errors = []

        for b in blocks:
            try:
                p = self.parse_block(b, default_subject=default_subject, default_topic=default_topic)
                parsed.append(p)
            except Exception as e:
                errors.append(f"{e} (block: {b[:120]})")
        return parsed, errors

    def parse_block(self, block: str, default_subject=None, default_topic=None) -> ParsedQuestion:
        lines = [l.rstrip() for l in block.splitlines() if l.strip() != ""]
        prompt = None
        choices = []
        answer_key = None
        
        # Defaults
        subject_obj = default_subject
        topic_obj = default_topic
        
        # Initialize slugs/titles from defaults if available, otherwise use placeholders
        if subject_obj:
            subject_slug = subject_obj.slug
            subject_title = subject_obj.title
        else:
            subject_slug = "unsorted"
            subject_title = ""

        if topic_obj:
            topic_slug = topic_obj.slug
            topic_title = topic_obj.title
        else:
            topic_slug = "general"
            topic_title = ""

        order = 0
        
        # Override if found in text
        for ln in lines:
            m = RE_Q.match(ln)
            if m:
                prompt = m.group(1).strip()
                continue
            m = RE_CHOICE.match(ln)
            if m:
                choices.append({"key": m.group(1).upper(), "text": m.group(2).strip()})
                continue
            m = RE_ANSWER.match(ln)
            if m:
                # ... existing answer logic ...
                answer_val = m.group(1).strip()
                if re.match(r"^[A-Za-z]$", answer_val):
                    answer_key = answer_val.upper()
                else:
                    found_key = None
                    for c in choices:
                        if c["key"] == answer_val.upper():
                            found_key = c["key"]
                            break
                    if not found_key:
                        for c in choices:
                            if c["text"].strip().lower() == answer_val.strip().lower():
                                found_key = c["key"]
                                break
                    if found_key:
                        answer_key = found_key
                    else:
                        answer_key = answer_val
                continue
            m = RE_SUBJECT.match(ln)
            if m:
                subject_title = m.group(1).strip()
                subject_slug = _normalize_slug(subject_title)
                continue
            m = RE_TOPIC.match(ln)
            if m:
                topic_title = m.group(1).strip()
                topic_slug = _normalize_slug(topic_title)
                continue
            m = RE_ORDER.match(ln)
            if m:
                order = int(m.group(1))
                continue
        
        if not prompt:
            raise ValueError("Missing prompt (Q:) in block")

        # Fallbacks if still empty
        if not subject_title and subject_slug == "unsorted":
             subject_title = "Unsorted"
        elif not subject_title:
             subject_title = subject_slug.replace("-", " ").title()

        if not topic_title and topic_slug == "general":
             topic_title = "General"
        elif not topic_title:
             topic_title = topic_slug.replace("-", " ").title()
             
        # IMPORTANT: If default_topic was passed, ensure we keep its exact slug/title unless explicitly overridden by text
        if topic_obj and not any(RE_TOPIC.match(l) for l in lines):
             topic_slug = topic_obj.slug
             topic_title = topic_obj.title
        
        # Same for subject
        if subject_obj and not any(RE_SUBJECT.match(l) for l in lines):
             subject_slug = subject_obj.slug
             subject_title = subject_obj.title

        return ParsedQuestion(
            prompt=prompt,
            choices=choices or None,
            answer_key=answer_key,
            subject_slug=subject_slug,
            subject_title=subject_title,
            topic_slug=topic_slug,
            topic_title=topic_title,
            order=order,
            is_premium=False,
            raw_block=block,
        )
