from django.db import models, migrations

class Migration(migrations.Migration):

    dependencies = [
        ('review', '0009_subject_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='subject',
            name='is_formula_collection',
            field=models.BooleanField(default=False, db_index=True, help_text='If True, this subject appears in the Formula Flashcards section.'),
        ),
    ]
