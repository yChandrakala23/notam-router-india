import os
import requests
from dotenv import load_dotenv

load_dotenv()

USER = os.getenv("AUTOROUTER_USER")
PASSWORD = os.getenv("AUTOROUTER_PASSWORD")

BASE_URL = "https://api.autorouter.aero/v1.0"

if not USER or not PASSWORD:
    raise RuntimeError(
        "AUTOROUTER_USER or AUTOROUTER_PASSWORD is missing from .env"
    )

# --------------------------------------------------
# 1. Request OAuth2 access token
# --------------------------------------------------

token_url = f"{BASE_URL}/oauth2/token"

token_data = {
    "grant_type": "client_credentials",
    "client_id": USER,
    "client_secret": PASSWORD,
}

print("Requesting Autorouter access token...")

token_response = requests.post(
    token_url,
    data=token_data,
    timeout=30,
)

print("Token status:", token_response.status_code)

if token_response.status_code != 200:
    print("Authentication failed.")
    print(token_response.text)
    raise SystemExit(1)

token_json = token_response.json()

access_token = token_json.get("access_token")

if not access_token:
    print("No access token returned.")
    print(token_json)
    raise SystemExit(1)

print("Authentication successful!")

# --------------------------------------------------
# 2. Check authenticated API access
# --------------------------------------------------

headers = {
    "Authorization": f"Bearer {access_token}"
}

version_response = requests.get(
    f"{BASE_URL}/system/version",
    headers=headers,
    timeout=30,
)

print("Version status:", version_response.status_code)
print(version_response.text[:1000])

# --------------------------------------------------
# 3. Test Indian NOTAM endpoint
# --------------------------------------------------

params = {
    "itemas": '["VIDP"]',
    "offset": 0,
    "limit": 10,
}

print("\nRequesting VIDP NOTAMs...")

notam_response = requests.get(
    f"{BASE_URL}/notam",
    headers=headers,
    params=params,
    timeout=30,
)

print("NOTAM status:", notam_response.status_code)
print(notam_response.text[:5000])