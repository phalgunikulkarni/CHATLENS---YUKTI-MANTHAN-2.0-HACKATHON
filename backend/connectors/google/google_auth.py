import os
import pickle
import logging
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/photoslibrary.readonly']

CLIENT_SECRETS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "client_secret.json")
SESSIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "storage", "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)

# Replace this with the actual URL your frontend will hit or a proxy URL
REDIRECT_URI = 'http://localhost:8000/api/connectors/google/callback'

def get_auth_url(account_id: str) -> str:
    """Generates the Google Auth URL."""
    if not os.path.exists(CLIENT_SECRETS_FILE):
        logger.error("client_secret.json not found")
        raise FileNotFoundError("Missing client_secret.json. Please add it to the backend root.")

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, 
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',
        state=account_id # pass the account id so the callback knows who this is for
    )
    return auth_url

def exchange_code(code: str, state: str) -> bool:
    """Exchanges the auth code for credentials and saves them."""
    if not os.path.exists(CLIENT_SECRETS_FILE):
        raise FileNotFoundError("Missing client_secret.json.")

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    
    flow.fetch_token(code=code)
    credentials = flow.credentials
    
    session_file = os.path.join(SESSIONS_DIR, f"{state}_google.pickle")
    with open(session_file, 'wb') as f:
        pickle.dump(credentials, f)
        
    return True

def get_credentials(account_id: str) -> Credentials:
    """Retrieves saved credentials."""
    session_file = os.path.join(SESSIONS_DIR, f"{account_id}_google.pickle")
    if not os.path.exists(session_file):
        return None
        
    with open(session_file, 'rb') as f:
        credentials = pickle.load(f)
        
    if credentials and credentials.expired and credentials.refresh_token:
        if not os.path.exists(CLIENT_SECRETS_FILE):
            logger.warning("Need to refresh token but client_secret.json is missing")
            return credentials
        credentials.refresh(Request())
        with open(session_file, 'wb') as f:
            pickle.dump(credentials, f)
            
    return credentials
