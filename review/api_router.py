# review/api_router.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
# Import viewsets from review.api - ensure review/api.py exists and defines these viewsets
from .api import (
    SubjectViewSet,
    FlashcardViewSet,
    ReviewFileViewSet,
    MockExamViewSet,
    AnalyticsViewSet,
    PaymentViewSet,
)

router = DefaultRouter()
router.register(r"subjects", SubjectViewSet, basename="subject")
router.register(r"flashcards", FlashcardViewSet, basename="flashcard")
router.register(r"review-files", ReviewFileViewSet, basename="reviewfile")
router.register(r"mock-exams", MockExamViewSet, basename="mockexam")
router.register(r"analytics", AnalyticsViewSet, basename="analytics")
router.register(r"payments", PaymentViewSet, basename="payments")

# expose urlpatterns for include()
urlpatterns = [
    path("", include(router.urls)),
    path("search/", views.search, name="search"),
]
