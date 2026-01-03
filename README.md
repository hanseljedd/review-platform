# Boardflash / Review Platform

A Django-based web application designed to help students prepare for board and professional examinations through structured review tools such as flashcards, formula summaries, blog articles, and mock exams.

## Overview

This project is an online board exam review platform focused on making review materials organized, accessible, and easy to use. It supports self-paced learning and serves as a foundation for multiple professional and licensure exams.

## Key Features

- Flashcards: topic-based fast recall for definitions, laws, and key terms
- Formula review: dedicated formula cards and summaries
- Educational blog posts: concept explanations and clarifications
- Mock exams: multiple-choice exams resembling real boards

## Tech Stack

- Backend: Django (Python)
- Frontend: HTML, CSS
- Database: SQLite (development), PostgreSQL (production)
- Env management: python-dotenv / django-environ
- Deployment: Render (Gunicorn, WhiteNoise)

## Screenshots

- Homepage: `screenshots/home.png`
- Flashcards: `screenshots/flashcards.png`
- Blog: `screenshots/blog.png`
- Mock Exams: `screenshots/mock-exam.png`

## Local Setup

- Create venv: `python -m venv .venv && .venv\\Scripts\\activate`
- Install deps: `pip install -r requirements.txt`
- Create `.env` based on `.env.example`
- Migrate: `python manage.py migrate`
- Run: `python manage.py runserver`

## Deploy on Render

This repo includes a `render.yaml` for zero-config deployment.

### Steps
- Push the repo to GitHub
- In Render, create a Web Service and select the repo
- Render will read `render.yaml`:
  - Build: `./build.sh` (installs, collects static, runs migrations)
  - Start: `gunicorn core.wsgi:application --workers=$WEB_CONCURRENCY --threads=4`
  - Env vars: `PYTHON_VERSION`, `SECRET_KEY` (auto), `DJANGO_SETTINGS_MODULE=core.settings.production`

### Recommended Environment Variables

- `DATABASE_URL` (PostgreSQL; use Render Internal URL)
- `ALLOWED_HOSTS` including your Render domain (e.g., `yourservice.onrender.com`)
- Optional S3 for uploads:
  - `AWS_STORAGE_BUCKET_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
  - `AWS_S3_REGION_NAME`, `AWS_S3_ENDPOINT_URL` (if applicable)
  - `MEDIA_URL` (optional CDN URL)

## Notes

- Static assets via WhiteNoise; `collectstatic` runs at build
- SQLite on Render is ephemeral; use PostgreSQL for production data
- Local `media/` is ephemeral in Render; configure S3 for persistence
