#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --no-input

# Run migrations
python manage.py migrate

# Optional: load initial data fixture (one-time)
if [ -n "$SEED_FIXTURE_PATH" ]; then
  echo "Loading fixture from $SEED_FIXTURE_PATH"
  python manage.py loaddata "$SEED_FIXTURE_PATH" || true
  echo "Verifying content counts after fixture load"
  python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','core.settings.production'); import django; django.setup(); from review.models import Subject, Topic, Question, MockExam; print({'subjects': Subject.objects.count(), 'topics': Topic.objects.count(), 'questions': Question.objects.count(), 'mock_exams': MockExam.objects.count()})" || true
fi

# Optional: copy seed media into media/ (one-time)
if [ -n "$SEED_MEDIA_PATH" ]; then
  mkdir -p media
  cp -R "$SEED_MEDIA_PATH"/* media/ || true
fi
