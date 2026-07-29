from celery import Celery
from celery.schedules import crontab
from config import settings

celery_app = Celery(
    "app",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["db1.tasks.task"]
)

celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.worker_concurrency = 4
celery_app.conf.broker_transport_options = {"visibility_timeout": 3600}

# Priority queues
celery_app.conf.task_routes = {
    "db1.tasks.task.send_welcome_email": {"queue": "high"},
    "db1.tasks.task.send_morning_notification": {"queue": "low"},
    "db1.tasks.task.process_outbox": {"queue": "high"},
    "db1.tasks.task.cancel_stale_orders": {"queue": "low"},
}

celery_app.conf.beat_schedule = {
    "send-morning-notifications": {
        "task": "db1.tasks.task.send_morning_notification",
        "schedule": crontab(hour=9, minute=0),
    },
    "process-outbox": {
        "task": "db1.tasks.task.process_outbox",
        "schedule": 5.0,
    },
    "cancel-stale-orders": {
        "task": "db1.tasks.task.cancel_stale_orders",
        "schedule": 300.0,  # каждые 5 минут
    },
}