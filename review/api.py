# review/api.py
from rest_framework import viewsets, permissions, pagination
from rest_framework.response import Response
from .models import Subject, Question, ReviewFile, MockExam, UserAccess, is_feature_enabled
from .serializers import SubjectSerializer, QuestionSerializer, ReviewFileSerializer, MockExamSerializer

class StandardResultsSetPagination(pagination.PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 1000

# Custom Permissions
class IsPremiumUser(permissions.BasePermission):
    """
    Allows access only to users with valid premium access.
    """
    def has_permission(self, request, view):
        return UserAccess.user_has_valid_access(request.user)

class IsAdminOrReadOnly(permissions.BasePermission):
    """
    The request is authenticated as a user, or is a read-only request.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_staff

# Viewsets
class SubjectViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Subject.objects.all().order_by("order")
    serializer_class = SubjectSerializer
    permission_classes = [permissions.AllowAny] # Subjects are public catalog

class FlashcardViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = QuestionSerializer
    pagination_class = StandardResultsSetPagination
    # Base permission: AllowAny for list (filtered by topic visibility), 
    # but specific objects might be premium.
    permission_classes = [permissions.AllowAny] 

    def get_queryset(self):
        """Return questions for the requested topic.
        Ordered mode is always accessible and must not be hidden by privacy joins.
        Random mode remains gated by feature/premium.
        """
        mode = (self.request.query_params.get("mode") or "ordered").lower()
        topic_slug = self.request.query_params.get("topic")
        if not topic_slug:
            return Question.objects.none()

        # Resolve the topic robustly
        topic_obj = None
        try:
            from .models import Topic
            topic_obj = Topic.objects.select_related("subject").filter(slug=topic_slug).first()
        except Exception:
            topic_obj = None
        if not topic_obj:
            return Question.objects.none()

        base_qs = Question.objects.filter(is_active=True, topic=topic_obj).select_related("topic", "topic__subject")

        if mode == "random":
            # Enforce Premium/Logged-in check for Random Mode
            if not UserAccess.user_has_valid_access(self.request.user):
                 # Fallback to ordered if not allowed (or return empty? Spec says "Ordered mode always available")
                 # Returning ordered mode silently is better UX than empty list for "free" users
                 return base_qs.order_by("order", "id")

            return base_qs.order_by("?")

        return base_qs.order_by("order", "id")

class ReviewFileViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Files are strictly for Premium users (unless free tier allows some, but here we assume premium).
    """
    queryset = ReviewFile.objects.all()
    serializer_class = ReviewFileSerializer
    permission_classes = [permissions.IsAuthenticated, IsPremiumUser]

class MockExamViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Mock exams are premium only.
    """
    queryset = MockExam.objects.all()
    serializer_class = MockExamSerializer
    permission_classes = [permissions.IsAuthenticated, IsPremiumUser]

class AnalyticsViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    def list(self, request):
        return Response({"detail": "Analytics endpoint placeholder"})

class PaymentViewSet(viewsets.ViewSet):
    # Payment status checks require auth
    permission_classes = [permissions.IsAuthenticated]
    def list(self, request):
        return Response({"detail": "Payments endpoint placeholder"})
