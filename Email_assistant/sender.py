import os
import base64
import warnings
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from email.mime.text import MIMEText

warnings.filterwarnings('ignore')
load_dotenv(override=True)

# --- Configuration ---

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")

# Scopes required for sending emails
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def get_gmail_service():
    """
    Authenticates using a refresh token and returns a Gmail API service object.
    """
    creds = Credentials(
        token=None,
        refresh_token=REFRESH_TOKEN,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token"
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    service = build('gmail', 'v1', credentials=creds)
    return service

def create_message(sender, to, subject, message_text):
    """
    Creates an email message.
    """
    message = MIMEText(message_text)
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {'raw': raw_message}

def send_email(recipient_email, subject, body):
    """
    Sends an email using the Gmail API.
    """
    service=get_gmail_service()
    sender_email = "krishusertest99@gmail.com"
    try:
        message = create_message(sender_email, recipient_email, subject, body)
        sent_message = service.users().messages().send(userId='me', body=message).execute()
        print(f"Message Id: {sent_message['id']}")
        return "Success!"
    except Exception as e:
        print(f"An error occurred: {e}")
        return "Failed!"
    

#Testing part

# if __name__ == '__main__':
#     gmail_service = get_gmail_service()

#     if gmail_service:
        
#         recipient_email = "abhiramkrishnayanam@gmail.com"
#         email_subject = "Automated Email from Python!"
#         email_body = "Hello,\n\nThis is an automated email sent using the Gmail API with Python.\n\nRegards,\nYour App"

#         send_email(recipient_email, email_subject, email_body)
#     else:
#         print("Failed to get Gmail service. Check your credentials and network connection.")

