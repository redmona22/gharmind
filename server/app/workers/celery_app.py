from celery import Celery

from app.config import settings

celery_app = Celery(
    "gharmind",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.process_message", "app.workers.reply"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    task_acks_late=True,  # a crashed worker's job is redelivered
    worker_prefetch_multiplier=1,
    timezone="UTC",
)
