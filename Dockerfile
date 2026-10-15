FROM python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --gid 10001 library \
    && useradd --uid 10001 --gid library \
        --no-create-home --no-log-init \
        --shell /usr/sbin/nologin library

COPY requirements.txt ./

RUN python -m pip install --no-cache-dir -r requirements.txt \
    && python -m pip check

COPY --chown=library:library . .

RUN mkdir -p /app/staticfiles \
    && chown library:library /app/staticfiles

USER 10001:10001

RUN DJANGO_SECRET_KEY=public-build-placeholder \
    DJANGO_DB_ENGINE=sqlite3 \
    DJANGO_DEBUG=false \
    python manage.py collectstatic --noinput

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/', timeout=3).close()"]

STOPSIGNAL SIGTERM

CMD ["gunicorn", "--no-control-socket", \
     "--bind", "0.0.0.0:8000", \
     "--worker-class", "gthread", "--workers", "2", "--threads", "2", \
     "--timeout", "30", "--graceful-timeout", "30", \
     "--access-logfile", "-", "--error-logfile", "-", \
     "config.wsgi:application"]