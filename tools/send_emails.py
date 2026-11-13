import logging
import smtplib
from email.message import EmailMessage
from typing import List


logger = logging.getLogger(__name__)


def send_email(subject: str, body: str, sender_email: str, recipient_email: str, bcc_recipients: List[str], smtp_server: str, smtp_port: int, username: str, password: str, author: str) -> bool:
    # Create the email message
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = f'"{author}" {sender_email}'
    msg['To'] = recipient_email
    if bcc_recipients:
        msg['Bcc'] = ', '.join(bcc_recipients)

    msg.set_content(body)
    # Format the message body as HTML with hyperlinks
    msg.add_alternative(body, subtype='html')

    try:
        # Connect to the SMTP server
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            # server.starttls()  # Use this for TLS connections
            server.login(username, password)

            # Send the email
            server.send_message(msg)
        print(f'Email sent successfully to {recipient_email}!')
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error(
            'SMTP authentication failed for sender %s. Use an application password '
            'when the provider requires two-factor authentication.',
            sender_email,
        )
        return False
    except (smtplib.SMTPException, OSError) as exc:
        logger.error('SMTP delivery failed for recipient %s: %s', recipient_email, exc)
        return False
    except Exception:
        logger.exception('Unexpected error while sending e-mail to %s', recipient_email)
        return False
