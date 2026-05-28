import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config import (
    YOUTUBE_CLIENT_SECRET_FILE,
    YOUTUBE_TOKEN_FILE,
    YOUTUBE_SCOPES,
    YOUTUBE_REDIRECT_URI,
)


def is_authenticated() -> bool:
    """Check if YouTube credentials exist and are valid."""
    if not os.path.exists(YOUTUBE_TOKEN_FILE):
        return False
    try:
        creds = _load_credentials()
        return creds is not None and creds.valid
    except Exception:
        return False


def get_auth_url() -> str:
    """Generate the Google OAuth2 authorization URL."""
    flow = Flow.from_client_secrets_file(
        str(YOUTUBE_CLIENT_SECRET_FILE),
        scopes=YOUTUBE_SCOPES,
        redirect_uri=YOUTUBE_REDIRECT_URI,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return auth_url


def handle_oauth_callback(authorization_code: str) -> bool:
    """Exchange authorization code for credentials and save them."""
    try:
        flow = Flow.from_client_secrets_file(
            str(YOUTUBE_CLIENT_SECRET_FILE),
            scopes=YOUTUBE_SCOPES,
            redirect_uri=YOUTUBE_REDIRECT_URI,
        )
        flow.fetch_token(code=authorization_code)
        creds = flow.credentials

        # Save credentials
        token_data = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes),
        }
        with open(YOUTUBE_TOKEN_FILE, "w") as f:
            json.dump(token_data, f)

        return True
    except Exception as e:
        print(f"OAuth callback error: {e}")
        return False


def _load_credentials() -> Credentials | None:
    """Load saved credentials from token file."""
    if not os.path.exists(YOUTUBE_TOKEN_FILE):
        return None

    with open(YOUTUBE_TOKEN_FILE, "r") as f:
        token_data = json.load(f)

    creds = Credentials(
        token=token_data["token"],
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data["token_uri"],
        client_id=token_data["client_id"],
        client_secret=token_data["client_secret"],
        scopes=token_data.get("scopes"),
    )

    # Refresh if expired
    if creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
        # Save refreshed token
        token_data["token"] = creds.token
        with open(YOUTUBE_TOKEN_FILE, "w") as f:
            json.dump(token_data, f)

    return creds


def upload_video(
    video_path: str,
    title: str,
    description: str,
    tags: list,
) -> str:
    """Upload a video to YouTube.

    Args:
        video_path: Path to the video file.
        title: Video title.
        description: Video description.
        tags: List of tags/hashtags.

    Returns:
        The YouTube video URL.
    """
    creds = _load_credentials()
    if not creds:
        raise ValueError("YouTube not authenticated. Please set up YouTube account first.")

    youtube = build("youtube", "v3", credentials=creds)

    # Clean tags (remove # prefix for YouTube tags)
    clean_tags = [tag.lstrip("#") for tag in tags]

    # Append hashtags to description
    hashtag_str = " ".join(tags)
    full_description = f"{description}\n\n{hashtag_str}"

    body = {
        "snippet": {
            "title": title,
            "description": full_description,
            "tags": clean_tags,
            "categoryId": "22",  # People & Blogs
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = request.execute()
    video_id = response["id"]
    return f"https://www.youtube.com/shorts/{video_id}"
