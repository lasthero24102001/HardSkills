import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from celery_app import celery_app
from config import settings
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


# убрали self — это не метод класса
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


# убрали self — это не метод класса
def send_morning_notification_on_failure(exc, task_id, args, kwargs, einfo):
    dead_letter_task.delay(
        task_name="send_morning_notification",
        args=list(args),
        kwargs=kwargs,
        error=str(exc)
    )

send_morning_notification.on_failure = send_morning_notification_on_failure