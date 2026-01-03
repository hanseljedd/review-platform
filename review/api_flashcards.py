# review/api_flashcards.py
from django.db.models import F
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.pagination import PageNumberPagination

from .models import Question, Topic
from .serializers import QuestionSerializer
from .models import is_feature_enabled  # ensure this import exists

class SmallPageNumberPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200

class FlashcardListAPIView(generics.ListAPIView):
    """
    GET /api/v1/flashcards/?topic=<slug>&mode=ordered|random&page=1&page_size=50
    - ordered: returns ordered by Question.order ASC (default)
    - random: returns randomized order — gated by feature flag + premium (server MUST enforce).
    """
    serializer_class = QuestionSerializer
    permission_classes = [AllowAny]
    pagination_class = SmallPageNumberPagination

    def get_queryset(self):
        mode = self.request.query_params.get("mode", "ordered").lower()
        topic_slug = self.request.query_params.get("topic")
        user = self.request.user

        # Resolve topic first to avoid over-filtering via joins
        topic = None
        if topic_slug:
            from .models import Topic
            topic = Topic.objects.filter(slug=topic_slug).select_related("subject").first()
        
        if topic is None:
            return Question.objects.none()

        qs = Question.objects.filter(is_active=True, topic=topic)

        # gating for random mode: server-side enforcement
        if mode == "random":
            if not is_feature_enabled("FEATURE_RANDOM_FLASHCARDS_ENABLED"):
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied(detail="Random flashcards are disabled.")
            from .models import UserAccess
            if is_feature_enabled("FEATURE_PREMIUM_LOGIN_REQUIRED") and not UserAccess.user_has_valid_access(user):
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied(detail="Premium access required for random mode.")
            return qs.order_by('?')
        # ordered mode: accessible to everyone (business rule), do not gate by privacy
        return qs.order_by("order", "id")
