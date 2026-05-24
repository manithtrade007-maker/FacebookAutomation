"""
token_refresh.py — Auto Facebook Token Refresher
Exchanges tokens for ALL pages in pages.json for new 60-day tokens.
Also updates Railway environment variables automatically.

Run manually:    python3 token_refresh.py
Auto (cron):     runs every 50 days via scheduler.py
"""

import os
import json
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv, set_key

load_dotenv()

APP_ID          = os.getenv("FB_APP_ID")
APP_SECRET      = os.getenv("FB_APP_SECRET")
RAILWAY_TOKEN   = os.getenv("RAILWAY_API_TOKEN")
RAILWAY_SVC_ID  = os.getenv("RAILWAY_SERVICE_ID")
RAILWAY_ENV_ID  = os.getenv("RAILWAY_ENVIRONMENT_ID")
RAILWAY_PROJ_ID = os.getenv("RAILWAY_PROJECT_ID")

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
PAGES_FILE = os.path.join(BASE_DIR, "pages.json")
ENV_FILE   = os.path.join(BASE_DIR, ".env")

_RAILWAY_MUTATION = """
mutation variableUpsert($input: VariableUpsertInput!) {
  variableUpsert(input: $input)
}
"""


# ── Token exchange ───────────────────────────────────────────────────────────

def exchange_token(current_token: str) -> str:
    """Exchange a token for a new 60-day long-lived token."""
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
        raise RuntimeError(f"Token exchange failed: {data}")
    expires_in = data.get("expires_in", 0)
    expires_at = datetime.now() + timedelta(seconds=expires_in)
    print(f"  New token obtained. Expires: {expires_at.strftime('%Y-%m-%d')}")
    return data["access_token"]


# ── pages.json update ────────────────────────────────────────────────────────

def load_pages() -> list:
    if not os.path.exists(PAGES_FILE):
        return []
    with open(PAGES_FILE) as f:
        return json.load(f)


def save_pages(pages: list) -> None:
    with open(PAGES_FILE, "w") as f:
        json.dump(pages, f, indent=2)


# ── Railway sync ─────────────────────────────────────────────────────────────

def _push_railway_var(name: str, value: str) -> bool:
    if not all([RAILWAY_TOKEN, RAILWAY_SVC_ID, RAILWAY_ENV_ID, RAILWAY_PROJ_ID]):
        return False
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
    return r.status_code == 200 and "errors" not in r.json()


def sync_pages_to_railway(pages: list) -> None:
    """Push the updated pages.json content to Railway as an env var."""
    if not all([RAILWAY_TOKEN, RAILWAY_SVC_ID, RAILWAY_ENV_ID, RAILWAY_PROJ_ID]):
        print("[TokenRefresh] Railway credentials not set — skipping Railway sync.")
        return
    pages_json = json.dumps(pages)
    ok = _push_railway_var("PAGES_JSON", pages_json)
    if ok:
        print("[TokenRefresh] Railway PAGES_JSON updated.")
    else:
        print("[TokenRefresh] Railway PAGES_JSON update failed.")

    _push_railway_var("TOKEN_LAST_REFRESHED", datetime.now().isoformat())


def redeploy_railway() -> None:
    if not all([RAILWAY_TOKEN, RAILWAY_SVC_ID]):
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


# ── Main ─────────────────────────────────────────────────────────────────────

def run_refresh() -> bool:
    """Refresh tokens for ALL pages in pages.json."""
    print(f"\n{'='*55}")
    print(f"  TOKEN REFRESH — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*55}")

    if not APP_ID or not APP_SECRET:
        print("[TokenRefresh] ERROR: FB_APP_ID or FB_APP_SECRET missing from .env")
        return False

    pages = load_pages()
    if not pages:
        print("[TokenRefresh] No pages found in pages.json")
        return False

    print(f"[TokenRefresh] Refreshing tokens for {len(pages)} page(s)...\n")
    any_success = False

    for i, page in enumerate(pages):
        name  = page.get("name", f"Page {i+1}")
        token = page.get("access_token", "")
        print(f"  [{i+1}/{len(pages)}] {name}")
        try:
            new_token = exchange_token(token)
            pages[i]["access_token"] = new_token
            any_success = True
        except Exception as e:
            print(f"  ❌ Failed: {e}")

    if any_success:
        save_pages(pages)
        set_key(ENV_FILE, "TOKEN_LAST_REFRESHED", datetime.now().isoformat())
        print(f"\n[TokenRefresh] pages.json updated with new tokens.")
        sync_pages_to_railway(pages)
        redeploy_railway()
        print(f"\n✅ Token refresh complete!")
    else:
        print(f"\n❌ All token refreshes failed.")

    print(f"{'='*55}\n")
    return any_success


if __name__ == "__main__":
    run_refresh()
