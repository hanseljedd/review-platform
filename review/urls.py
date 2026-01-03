# review/urls.py
from django.urls import path, include
from . import views, views_auth, views_extra

app_name = "review"

urlpatterns = [
    # Auth
    path("login/", views_auth.login_view, name="login"),
    # path("register/", views_auth.register_view, name="register"), # Registration disabled (Invite-only)
    path("logout/", views_auth.logout_view, name="logout"),

    # Main entry point is now the Landing Page
    path("", views.landing, name="landing"),
    
    # New Folder Navigation Flow
    path("subjects/<slug:subject_slug>/", views_extra.subject_folders, name="subject_folders"),
    path("subjects/<slug:subject_slug>/<str:folder_name>/", views_extra.folder_topics, name="folder_topics"),

    # The old "Home" (Subject List) is moved to /dashboard/
    path("", views.landing, name="landing"),
    
    # path("landing/", views.landing, name="landing"), # Removed as it is now root
    path("pricing/", views.pricing, name="pricing"),
    path("pricing/upload/", views.upload_payment, name="upload_payment"),  # New Payment Upload URL
    path("flashcards/<slug:topic_slug>/", views.flashcards, name="flashcards"),
    path("flashcards/", views.flashcards_hub, name="flashcards_hub"),
    path("files/", views.review_files, name="review_files"),
    path("exams/", views.mock_exams, name="mock_exams"),
    path("exams/<uuid:exam_id>/take/", views.take_mock_exam, name="take_mock_exam"),
    path("exams/session/<uuid:session_id>/result/", views.exam_result, name="exam_result"),
    path("info/", views.info_page, name="info"),
    path("health/content", views_extra.content_health, name="content_health"),
    
    # API endpoints (Master Spec: /api/v1/)
    path("api/v1/", include("review.api_router")),
]
