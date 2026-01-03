# core/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from review.views_flashcards import flashcard_view
from review.api_flashcards import FlashcardListAPIView
from review import views as review_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("blog/", include("blog.urls")),
    path("ckeditor/", include("ckeditor_uploader.urls")),
    path("api/v1/", include("review.api_router")),
    path("", include("review.urls")),
    path("robots.txt", review_views.robots_txt, name="robots-txt"),
    path("sitemap.xml", review_views.sitemap_xml, name="sitemap-xml"),
    path("flashcards/<slug:topic_slug>/", flashcard_view, name="flashcards-page"),
    path("api/v1/flashcards/", FlashcardListAPIView.as_view(), name="api-flashcards"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)