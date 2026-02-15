# jarvis/integrations/calendar_integration.py - Google Calendar Integration

import logging
import pickle
import os
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient import discovery

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/calendar']

class CalendarIntegration:
    """Google Calendar integration."""
    
    def __init__(self, credentials_file='jarvis/integrations/credentials.json'):
        self.credentials_file = credentials_file
        self.service = None
        self.authenticated = False
        
        try:
            self._authenticate()
        except Exception as e:
            logger.warning(f"⚠️ Calendar authentication failed: {e}")

    def _authenticate(self):
        """Authenticate with Google Calendar API."""
        creds = None
        
        if os.path.exists('jarvis/integrations/calendar_token.pickle'):
            with open('jarvis/integrations/calendar_token.pickle', 'rb') as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if os.path.exists(self.credentials_file):
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, SCOPES)
                    creds = flow.run_local_server(port=0)
        
        with open('jarvis/integrations/calendar_token.pickle', 'wb') as token:
            pickle.dump(creds, token)
        
        self.service = discovery.build('calendar', 'v3', credentials=creds)
        self.authenticated = True
        logger.info("✅ Calendar authenticated")

    def create_event(self, title: str, start_time: str, end_time: str, description: str = ""):
        """Create a calendar event."""
        if not self.authenticated:
            return "Calendar not authenticated"
        
        try:
            event = {
                'summary': title,
                'description': description,
                'start': {'dateTime': start_time, 'timeZone': 'Asia/Karachi'},
                'end': {'dateTime': end_time, 'timeZone': 'Asia/Karachi'},
            }
            
            result = self.service.events().insert(
                calendarId='primary', body=event).execute()
            
            logger.info(f"✅ Event created: {title}")
            return f"Event '{title}' created successfully"
        except Exception as e:
            logger.error(f"Error creating event: {e}")
            return f"Failed to create event: {str(e)}"

    def get_upcoming_events(self, days: int = 7):
        """Get upcoming events."""
        if not self.authenticated:
            return []
        
        try:
            now = datetime.utcnow().isoformat() + 'Z'
            later = (datetime.utcnow() + timedelta(days=days)).isoformat() + 'Z'
            
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=now,
                timeMax=later,
                maxResults=10,
                singleEvents=True,
                orderBy='startTime').execute()
            
            events = []
            for event in events_result.get('items', []):
                events.append({
                    'summary': event.get('summary', 'No Title'),
                    'start': event['start'].get('dateTime', event['start'].get('date')),
                    'description': event.get('description', '')
                })
            
            return events
        except Exception as e:
            logger.error(f"Error getting events: {e}")
            return []

    def check_availability(self, start_time: str, end_time: str) -> bool:
        """Check if a time slot is available."""
        if not self.authenticated:
            return True
        
        try:
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=start_time,
                timeMax=end_time,
                maxResults=1).execute()
            
            return len(events_result.get('items', [])) == 0
        except Exception as e:
            logger.error(f"Error checking availability: {e}")
            return True
