from django.core.mail.backends.base import BaseEmailBackend
import requests
import json
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class ResendBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        
        api_key = getattr(settings, "RESEND_API_KEY", None)
        if not api_key:
            logger.error("RESEND_API_KEY is not configured in settings.")
            if not self.fail_silently:
                raise ValueError("RESEND_API_KEY is missing from settings.")
            return 0
            
        sent_count = 0
        for message in email_messages:
            try:
                html_content = ""
                text_content = message.body
                
                # Retrieve HTML content if it's a multi-alternative email
                if hasattr(message, "alternatives"):
                    for alt, mimetype in message.alternatives:
                        if mimetype == "text/html":
                            html_content = alt
                            break
                
                # Construct payload
                payload = {
                    "from": message.from_email,
                    "to": list(message.to),
                    "subject": message.subject,
                }
                
                if html_content:
                    payload["html"] = html_content
                else:
                    payload["text"] = text_content
                    
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                
                timeout = getattr(settings, "EMAIL_TIMEOUT", 10)
                response = requests.post(
                    "https://api.resend.com/emails",
                    data=json.dumps(payload),
                    headers=headers,
                    timeout=timeout
                )
                
                if response.status_code in [200, 201]:
                    sent_count += 1
                else:
                    logger.error(
                        f"Failed to send email via Resend API. "
                        f"Status code: {response.status_code}, Response: {response.text}"
                    )
                    if not self.fail_silently:
                        raise Exception(f"Resend API error: {response.text}")
            except Exception as e:
                logger.error(f"Error sending email via Resend: {str(e)}")
                if not self.fail_silently:
                    raise e
                    
        return sent_count
