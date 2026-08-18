#!/usr/bin/env python
"""WSGI config para produção (Vercel / serverless)."""

import os

from django.core.wsgi import get_wsgi_application

# Vercel injeta VERCEL=1 automaticamente em todos os deploys
if os.getenv("VERCEL"):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.vercel")
else:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

application = get_wsgi_application()
