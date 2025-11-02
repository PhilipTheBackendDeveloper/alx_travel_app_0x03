from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

@shared_task
def send_booking_email(booking_id, user_email):
    """
    Sends a booking confirmation email asynchronously.
    """
    subject = "Booking Confirmation"
    message = f"Your booking (ID: {booking_id}) has been confirmed. Thank you for using our service."
    email_from = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user_email]
    send_mail(subject, message, email_from, recipient_list)
    return f"Email sent to {user_email}"
