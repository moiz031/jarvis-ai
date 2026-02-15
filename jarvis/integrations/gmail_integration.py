# jarvis/integrations/gmail_integration.py - Gmail Integration

import logging
import pickle
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient import discovery

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

class GmailIntegration:
    """Gmail integration for email operations."""
    
    def __init__(self, credentials_file='jarvis/integrations/credentials.json'):
        self.credentials_file = credentials_file
        self.service = None
        self.authenticated = False
        
        # Try to authenticate
        try:
            self._authenticate()
        except Exception as e:
            logger.warning(f"⚠️ Gmail authentication failed: {e}")

    def _authenticate(self):
        """Authenticate with Gmail API."""
        creds = None
        
        # Load saved credentials
        if os.path.exists('jarvis/integrations/token.pickle'):
            with open('jarvis/integrations/token.pickle', 'rb') as token:
                creds = pickle.load(token)
        
        # Get new credentials if needed
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if os.path.exists(self.credentials_file):
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, SCOPES)
                    creds = flow.run_local_server(port=0)
        
        # Save credentials
        with open('jarvis/integrations/token.pickle', 'wb') as token:
            pickle.dump(creds, token)
        
        self.service = discovery.build('gmail', 'v1', credentials=creds)
        self.authenticated = True
        logger.info("✅ Gmail authenticated")

    def send_email(self, to: str, subject: str, body: str):
        """Send an email."""
        if not self.authenticated:
            return "Gmail not authenticated"
        
        try:
            from email.mime.text import MIMEText
            import base64
            
            message = MIMEText(body)
            message['to'] = to
            message['subject'] = subject
            
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            send_message = {'raw': raw}
            
            result = self.service.users().messages().send(
                userId='me', body=send_message).execute()
            
            logger.info(f"✅ Email sent to {to}")
            return f"Email sent successfully to {to}"
        except Exception as e:
            logger.error(f"❌ Error sending email: {e}")
            return f"Failed to send email: {str(e)}"

    def get_unread_count(self):
        """Get count of unread emails."""
        if not self.authenticated:
            return 0
        
        try:
            results = self.service.users().messages().list(
                userId='me', q='is:unread').execute()
            return results.get('resultSizeEstimate', 0)
        except Exception as e:
            logger.error(f"Error getting unread count: {e}")
            return 0

    def read_recent_emails(self, limit: int = 5):
        """Read recent emails."""
        if not self.authenticated:
            return []
        
        try:
            results = self.service.users().messages().list(
                userId='me', maxResults=limit).execute()
            
            messages = []
            for msg in results.get('messages', []):
                msg_data = self.service.users().messages().get(
                    userId='me', id=msg['id']).execute()
                
                headers = msg_data['payload']['headers']
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
                
                messages.append({
                    'subject': subject,
                    'from': sender,
                    'id': msg['id']
                })
            
            return messages
        except Exception as e:
            logger.error(f"Error reading emails: {e}")
            return []
