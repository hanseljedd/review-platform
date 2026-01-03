from django.db import models
from django.conf import settings
from django.utils.text import slugify
from ckeditor_uploader.fields import RichTextUploadingField

class BlogPost(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, max_length=200, blank=True)
    cover_image = models.ImageField(upload_to='blog/covers/', blank=True, null=True)
    content = RichTextUploadingField(help_text="Main content of the blog post. Supports images, highlighting, and formatting.")
    summary = models.TextField(max_length=500, help_text="Short summary for SEO and previews.")
    
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    published_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(default=True)
    
    # SEO Fields
    seo_title = models.CharField(max_length=70, blank=True, help_text="SEO Title (defaults to title)")
    seo_description = models.CharField(max_length=160, blank=True, help_text="SEO Description (defaults to summary)")
    
    class Meta:
        ordering = ['-published_at']
        verbose_name = "Blog Post"
        verbose_name_plural = "Blog Posts"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        if not self.seo_title:
            self.seo_title = self.title
        if not self.seo_description:
            self.seo_description = self.summary[:160]
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('blog:post_detail', kwargs={'slug': self.slug})
