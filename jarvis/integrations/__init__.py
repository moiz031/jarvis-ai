# jarvis/integrations/__init__.py
"""Jarvis integrations module.

Provides integration classes for Gmail, Calendar, and Storage services.
"""

from .gmail_integration import GmailIntegration
from .calendar_integration import CalendarIntegration
from .storage_integration import GoogleDriveIntegration, LocalStorageIntegration

__all__ = [
    'GmailIntegration',
    'CalendarIntegration',
    'GoogleDriveIntegration',
    'LocalStorageIntegration'
]
