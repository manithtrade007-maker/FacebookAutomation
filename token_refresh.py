"""
token_refresh.py — Auto Facebook Token Refresher
Exchanges the current FB token for a new 60-day token.
Updates local .env AND Railway environment variables automatically.

Run manually:    python3 token_refresh.py
Auto (cron):     runs every 50 days via scheduler.py
"""

import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv, set_key

load_dotenv()

# ── Config ───────────────────────────────────────────────────────────────────
APP_ID          = os.getenv("FB_APP_ID")
APP_SECRET      = os.getenv("FB_APP_SECRET")
FB_ACCESS_TOKEN = os.getenv("FB_ACCESS_TOKEN")
RAILWAY_TOKEN   = os.getenv("RAILWAY_API_TOKEN")
RAILWAY_SVC_ID  = os.getenv("RAILWAY_SERVICE_ID")
RAILWAY_ENV_ID  = os.getenv("RAILWAY_ENVIRONMENT_ID")
RAILWAY_PROJ_ID = os.getenv("RAILWAY_PROJECT_ID")
ENV_FILE        = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

_RAILWAY_MUTATION = """
mutation variableUpsert($input: VariableUpsertInput!) {
  variableUpsert(input: $input)
}
"""


def refresh_token(current_token: str) -> str:
    """Exchange current token for a new 60-day long-lived token."""
    print("[TokenRefresh] Exchanging token with Facebook...")
    r = requests.get(
        "https://graph.facebook.com/v19.0/oauth/access_token",
        params={
            "grant_type":        "fb_exchange_token",
            "client_id":         APP_ID,
            "client_secret":     APP_SECRET,
            "fb_exchange_token": current_token,
        },
        timeout=15,
    )
    data = r.json()
    if "access_token" not in data:
        raise RuntimeError(f"Facebook token exchange failed: {data}")

    new_token  = data["access_token"]
    expires_in = data.get("expires_in", 0)
    expires_at = datetime.now() + timedelta(seconds=expires_in)
    print(f"[TokenRefresh] New token obtained. Expires: {expires_at.strftime('%Y-%m-%d')}")
    return new_token


def update_env_file(new_token: str) -> None:
    """Updates the local .env file with the new token and refresh timestamp."""
    set_key(ENV_FILE, "FB_ACCESS_TOKEN", new_token)
    set_key(ENV_FILE, "TOKEN_LAST_REFRESHED", datetime.now().isoformat())
    print("[TokenRefresh] .env updated.")


def _push_railway_var(name: str, value: str) -> bool:
    """Push a single variable to Railway via GraphQL API."""
    r = requests.post(
        "https://backboard.railway.app/graphql/v2",
        json={
            "query": _RAILWAY_MUTATION,
            "variables": {
                "input": {
                    "projectId":     RAILWAY_PROJ_ID,
                    "serviceId":     RAILWAY_SVC_ID,
                    "environmentId": RAILWAY_ENV_ID,
                    "name":          name,
                    "value":         value,
                }
            },
        },
        headers={
            "Authorization": f"Bearer {RAILWAY_TOKEN}",
            "Content-Type":  "application/json",
        },
        timeout=15,
    )
    if r.status_code == 200 and "errors" not in r.json():
        print(f"[TokenRefresh] Railway {name} updated.")
        return True
    print(f"[TokenRefresh] Railway {name} update failed: {r.text}")
    return False


def update_railway(new_token: str) -> bool:
    """Updates FB_ACCESS_TOKEN and TOKEN_LAST_REFRESHED in Railway."""
    if not RAILWAY_TOKEN or not RAILWAY_SVC_ID or not RAILWAY_ENV_ID or not RAILWAY_PROJ_ID:
        print("[TokenRefresh] Railway credentials not set — skipping Railway update.")
        return False

    ok1 = _push_railway_var("FB_ACCESS_TOKEN", new_token)
    ok2 = _push_railway_var("TOKEN_LAST_REFRESHED", datetime.now().isoformat())
    return ok1 and ok2


def redeploy_railway() -> None:
    """Triggers a Railway redeploy so the new token takes effect."""
    if not RAILWAY_TOKEN or not RAILWAY_SVC_ID:
        return

    r = requests.post(
        "https://backboard.railway.app/graphql/v2",
        json={
            "query": """
            mutation serviceInstanceRedeploy($serviceId: String!) {
              serviceInstanceRedeploy(serviceId: $serviceId)
            }
            """,
            "variables": {"serviceId": RAILWAY_SVC_ID},
        },
        headers={
            "Authorization": f"Bearer {RAILWAY_TOKEN}",
            "Content-Type":  "application/json",
        },
        timeout=15,
    )
    if r.status_code == 200:
        print("[TokenRefresh] Railway redeploy triggered.")


def run_refresh() -> str:
    """Main function — refreshes the token and updates all locations."""
    print(f"\n{'='*50}")
    print(f"  TOKEN REFRESH — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")

    if not FB_ACCESS_TOKEN:
        print("[TokenRefresh] ERROR: FB_ACCESS_TOKEN not found in .env")
        return ""

    if not APP_ID or not APP_SECRET:
        print("[TokenRefresh] ERROR: FB_APP_ID or FB_APP_SECRET not set in .env")
        return ""

    new_token = refresh_token(FB_ACCESS_TOKEN)
    update_env_file(new_token)
    update_railway(new_token)
    redeploy_railway()

    print(f"\n✅ Token refreshed successfully!")
    print(f"{'='*50}\n")
    return new_token


if __name__ == "__main__":
    run_refresh()
