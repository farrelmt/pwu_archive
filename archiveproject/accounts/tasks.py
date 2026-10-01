import base64

from celery import shared_task
from django.core.mail import EmailMessage


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={'max_retries': 3},
)
def send_email_message(subject, body, recipients, attachments=None):
    """Send an email outside the web request process."""
    email = EmailMessage(subject=subject, body=body, to=recipients)
    for attachment in attachments or []:
        email.attach(
            attachment['name'],
            base64.b64decode(attachment['content']),
            attachment.get('content_type'),
        )
    return email.send(fail_silently=False)


def encoded_attachment(uploaded_file):
    if not uploaded_file:
        return None
    return {
        'name': uploaded_file.name,
        'content': base64.b64encode(uploaded_file.read()).decode('ascii'),
        'content_type': uploaded_file.content_type,
    }


def queue_email_message(*, subject, body, recipients, attachments=None):
    try:
        send_email_message.delay(
            subject,
            body,
            recipients,
            attachments or [],
        )
    except Exception:
        return False
    return True
