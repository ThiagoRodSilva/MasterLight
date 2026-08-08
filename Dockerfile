# syntax=docker/dockerfile:1.6
FROM python:3.12-slim AS builder
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update && apt-get install --no-install-recommends -y \
    build-essential libmariadb-dev pkg-config && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt


FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DJANGO_SETTINGS_MODULE=config.settings.prod
WORKDIR /app
RUN apt-get update && apt-get install --no-install-recommends -y \
    libmariadb3 libjpeg62-turbo && rm -rf /var/lib/apt/lists/*
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . /app/
RUN python manage.py collectstatic --noinput
EXPOSE 8000
CMD ["gunicorn", "-c", "gunicorn.conf.py", "config.wsgi:application"]
