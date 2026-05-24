import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

def send_outreach_email(
    sender_email: str,
    sender_password: str,
    recipient_email: str,
    subject: str,
    body: str,
    resume_bytes: bytes,
    resume_filename: str = "Resume.pdf",
    smtp_server: str = "smtp.gmail.com",
    smtp_port: int = 587
) -> bool:
    """
    Sends an email with a PDF attachment using SMTP.
    Works with Gmail App Passwords.
    """
    if not sender_email or not sender_password or not recipient_email:
        raise ValueError("Sender email, sender password, and recipient email are all required.")
        
    try:
        # Create message container
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        # Attach email body
        msg.attach(MIMEText(body, 'plain'))
        
        # Attach resume PDF
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(resume_bytes)
        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename="{resume_filename}"'
        )
        msg.attach(part)
        
        # Connect to SMTP server and send email
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Upgrade connection to secure TLS
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.quit()
        
        return True
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        raise e
