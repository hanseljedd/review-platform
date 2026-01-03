# review/serializers.py
from rest_framework import serializers
from .models import Subject, Question, ReviewFile, MockExam, Topic

# ---------- Subjects ----------
class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ["id", "slug", "title", "description", "order"]


# ---------- Topic (mini) ----------
class TopicMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = ("slug", "title")  # Spec: topic (slug + title)


# ---------- Questions (frontend expects `answer`) ----------
class QuestionSerializer(serializers.ModelSerializer):
    topic = TopicMiniSerializer(read_only=True)
    
    class Meta:
        model = Question
        fields = (
            "id",
            "topic",
            "order",
            "prompt",
            "choices",       # [{"key": "A", "text": "Hydrogen"}]
            "answer",        # Actual value
            "answer_type",
            "is_premium",
            "created_at",
            "explanation",   # Good to have
        )
        read_only_fields = ("id", "created_at")


# ---------- Review file ----------
class ReviewFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewFile
        fields = ["id", "title", "file", "is_premium", "metadata", "description"]


# ---------- Mock exam ----------
class MockExamSerializer(serializers.ModelSerializer):
    class Meta:
        model = MockExam
        fields = ["id", "title", "description", "duration_minutes", "is_premium"]
