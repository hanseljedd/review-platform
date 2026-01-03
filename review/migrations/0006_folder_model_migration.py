from django.db import migrations, models
import django.db.models.deletion
import uuid

def migrate_folders(apps, schema_editor):
    Subject = apps.get_model("review", "Subject")
    Topic = apps.get_model("review", "Topic")
    Folder = apps.get_model("review", "Folder")
    
    # Iterate all topics, create Folder if needed, link it
    for topic in Topic.objects.all():
        folder_name = topic.folder or "General"
        # Find or create Folder for this subject
        folder_obj, created = Folder.objects.get_or_create(
            subject=topic.subject,
            title=folder_name,
            defaults={"order": 0}
        )
        topic.folder_ref = folder_obj
        topic.save()

class Migration(migrations.Migration):

    dependencies = [
        ('review', '0005_topic_folder'),
    ]

    operations = [
        migrations.CreateModel(
            name='Folder',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=255)),
                ('order', models.PositiveIntegerField(db_index=True, default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='folders', to='review.subject')),
            ],
            options={
                'verbose_name': 'Folder',
                'verbose_name_plural': 'Folders',
                'ordering': ('subject', 'order', 'title'),
                'unique_together': {('subject', 'title')},
            },
        ),
        migrations.AddField(
            model_name='topic',
            name='folder_ref',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='topics', to='review.folder'),
        ),
        migrations.AlterField(
            model_name='topic',
            name='folder',
            field=models.CharField(blank=True, db_index=True, default='General', help_text='Deprecated. Use folder_ref.', max_length=255),
        ),
        migrations.RunPython(migrate_folders),
    ]
