FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY backend/requirements*.txt ./
RUN python -m pip install -r requirements-production.txt \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home app

COPY --chown=app:app backend/ ./
RUN mkdir -p /app/staticfiles && chown app:app /app/staticfiles

USER app
EXPOSE 8000

# 只启动服务；迁移和 collectstatic 由部署人员单独执行一次。
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "4", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-", "--forwarded-allow-ips", "*"]

