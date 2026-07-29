import json
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from sqlalchemy import select

from celery_app import celery_app
from config import settings
from db1.Database.database import async_factory
from db1.models.Base1 import OutboxEvent
import logging
import redis

logger = logging.getLogger(__name__)
redis_client = redis.from_url(settings.REDIS_URL)


def send_email_smtp(to_email: str, subject: str, body: str):
    msg = MIMEMultipart()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM, to_email, msg.as_string())


# DLQ таск
@celery_app.task
def dead_letter_task(task_name: str, args: list, kwargs: dict, error: str):
    logger.error(
        f"DLQ: task={task_name} | "
        f"error={error} | "
        f"args={args} | "
        f"kwargs={kwargs}"
    )


# Welcome email таск с идемпотентным ключом
@celery_app.task(
    bind=True,
    max_retries=3,
    acks_late=True,
    soft_time_limit=60,
    time_limit=120,
    rate_limit="100/m"
)
def send_welcome_email(self, user_id: int, email: str):
    idempotent_key = f"welcome_email_sent:{user_id}"
    if not redis_client.set(idempotent_key, "1", nx=True, ex=86400):
        logger.info(f"Welcome email already sent to {email} — skipping")
        return

    try:
        logger.info(f"Sending welcome email to {email}")
        send_email_smtp(
            to_email=email,
            subject="Добро пожаловать!",
            body=f"<h1>Привет!</h1><p>Ваш аккаунт создан. ID: {user_id}</p>"
        )
        logger.info(f"Welcome email sent to {email}")
    except Exception as e:
        redis_client.delete(idempotent_key)
        logger.error(f"Failed to send email to {email}: {e}")
        raise self.retry(exc=e, countdown=2 ** self.request.retries)


def send_welcome_email_on_failure(exc, task_id, args, kwargs, einfo):
    dead_letter_task.delay(
        task_name="send_welcome_email",
        args=list(args),
        kwargs=kwargs,
        error=str(exc)
    )

send_welcome_email.on_failure = send_welcome_email_on_failure


# Morning notification таск с идемпотентным ключом
@celery_app.task(
    bind=True,
    max_retries=3,
    acks_late=True,
    soft_time_limit=120,
    time_limit=240
)
def send_morning_notification(self):
    from datetime import date
    idempotent_key = f"morning_notification:{date.today()}"
    if not redis_client.set(idempotent_key, "1", nx=True, ex=86400):
        logger.info("Morning notification already sent today — skipping")
        return

    try:
        logger.info("Sending morning notifications to all users")
    except Exception as e:
        redis_client.delete(idempotent_key)
        logger.error(f"Morning notification failed: {e}")
        raise self.retry(exc=e, countdown=2 ** self.request.retries)


def send_morning_notification_on_failure(exc, task_id, args, kwargs, einfo):
    dead_letter_task.delay(
        task_name="send_morning_notification",
        args=list(args),
        kwargs=kwargs,
        error=str(exc)
    )

send_morning_notification.on_failure = send_morning_notification_on_failure


# ==========================================
# Outbox processing — доставка событий заказов
# ==========================================

async def notify_payment_service(payload: dict):
    # TODO: заменить на реальный вызов Payme/Click API, когда появится merchant_id
    logger.info(f"[MOCK] Payment service notified: {payload}")


@celery_app.task(
    bind=True,
    max_retries=5,
    acks_late=True,
    soft_time_limit=30,
    time_limit=60,
)
def process_outbox(self):
    import asyncio

    async def _process():
        async with async_factory() as db:
            result = await db.execute(
                select(OutboxEvent)
                .where(OutboxEvent.status == "pending")
                .limit(10)
                .with_for_update(skip_locked=True)
            )
            events = result.scalars().all()

            for event in events:
                try:
                    payload = json.loads(event.payload)

                    if event.event_type == "order_created":
                        await notify_payment_service(payload)

                    event.status = "sent"
                    event.processed_at = datetime.utcnow()

                except Exception as e:
                    event.status = "failed"
                    logger.error(f"Outbox event {event.id} failed: {e}")

            await db.commit()

    asyncio.run(_process())


def process_outbox_on_failure(exc, task_id, args, kwargs, einfo):
    dead_letter_task.delay(
        task_name="process_outbox",
        args=list(args),
        kwargs=kwargs,
        error=str(exc)
    )

process_outbox.on_failure = process_outbox_on_failure


# ==========================================
# Cancel stale pending orders — возврат stock
# для заказов, которые никто не оплатил
# ==========================================

@celery_app.task(
    bind=True,
    max_retries=3,
    acks_late=True,
    soft_time_limit=60,
    time_limit=120,
)
def cancel_stale_orders(self):
    import asyncio
    from db1.Services.services import OrderService

    async def _process():
        async with async_factory() as db:
            service = OrderService(db)
            count = await service.cancel_stale_orders(older_than_minutes=15)
            if count:
                logger.info(f"Cancelled {count} stale pending orders")

    asyncio.run(_process())


def cancel_stale_orders_on_failure(exc, task_id, args, kwargs, einfo):
    dead_letter_task.delay(
        task_name="cancel_stale_orders",
        args=list(args),
        kwargs=kwargs,
        error=str(exc)
    )

cancel_stale_orders.on_failure = cancel_stale_orders_on_failure