# jarvis/integrations/__init__.py
"""Jarvis integrations module.

Provides integration classes for Gmail, Calendar, and Storage services.
Optional provider imports are guarded so base package import stays stable.
"""

from typing import TYPE_CHECKING

from .storage_integration import GoogleDriveIntegration, LocalStorageIntegration

if TYPE_CHECKING:
    from .gmail_integration import GmailIntegration
    from .calendar_integration import CalendarIntegration
else:
    try:
        from .gmail_integration import GmailIntegration
    except Exception:
        class GmailIntegration:  # type: ignore[no-redef]
            def __init__(self, *args, **kwargs):
                raise ImportError(
                    "Gmail integration dependencies missing. Install Google API packages "
                    "(google-api-python-client, google-auth, google-auth-oauthlib)."
                )

    try:
        from .calendar_integration import CalendarIntegration
    except Exception:
        class CalendarIntegration:  # type: ignore[no-redef]
            def __init__(self, *args, **kwargs):
                raise ImportError(
                    "Calendar integration dependencies missing. Install Google API packages "
                    "(google-api-python-client, google-auth, google-auth-oauthlib)."
                )

__all__ = [
    "GmailIntegration",
    "CalendarIntegration",
    "GoogleDriveIntegration",
    "LocalStorageIntegration",
]
