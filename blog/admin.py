from django.contrib import admin
from .models import BlogPost

@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_published', 'published_at', 'author')
    list_filter = ('is_published', 'published_at', 'author')
    search_fields = ('title', 'content', 'summary')
    prepopulated_fields = {'slug': ('title',)}
