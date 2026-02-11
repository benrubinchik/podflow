"""OAuth2 flow + token caching for Google APIs."""

from __future__ import annotations

import json
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from podflow.utils.logging import get_logger

log = get_logger(__name__)

YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_SCOPES = [YOUTUBE_UPLOAD_SCOPE]


def get_authenticated_credentials(
    client_secrets_file: str,
    token_file: str,
    scopes: list[str] | None = None,
) -> Credentials:
    """Get authenticated Google OAuth2 credentials, using cached tokens when possible."""
    scopes = scopes or YOUTUBE_SCOPES
    token_path = Path(token_file)
    creds = None

    # Try to load cached token
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), scopes)
        except (json.JSONDecodeError, ValueError) as e:
            log.warning("Cached token invalid, re-authenticating: %s", e)
            creds = None

    # Refresh or re-authenticate
    if creds and creds.expired and creds.refresh_token:
        log.info("Refreshing expired OAuth2 token")
        creds.refresh(Request())
    elif not creds or not creds.valid:
        secrets_path = Path(client_secrets_file)
        if not secrets_path.exists():
            raise FileNotFoundError(
                f"OAuth2 client secrets file not found: {client_secrets_file}\n"
                "Download it from the Google Cloud Console under "
                "APIs & Services > Credentials."
            )
        log.info("Starting OAuth2 authorization flow (browser will open)")
        flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), scopes)
        creds = flow.run_local_server(port=0)

    # Cache the token
    token_path.write_text(creds.to_json(), encoding="utf-8")
    log.info("OAuth2 credentials saved to %s", token_path)

    return creds
