"""
create_pages.py — Facebook Page Creator
Creates new Facebook Pages automatically via the Graph API and adds them to pages.json.

Usage:
  python3 create_pages.py

You need a USER access token (not a page token).
Get one from: developers.facebook.com/tools/explorer
Select: "Get User Access Token" with permissions:
  pages_manage_posts, pages_show_list, pages_read_engagement, publish_video
"""

import json
import os
import requests
import sys
from dotenv import load_dotenv, set_key

load_dotenv()

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
PAGES_FILE = os.path.join(BASE_DIR, "pages.json")
ENV_FILE   = os.path.join(BASE_DIR, ".env")

FB_GRAPH   = "https://graph.facebook.com/v19.0"
APP_ID     = os.getenv("FB_APP_ID")
APP_SECRET = os.getenv("FB_APP_SECRET")

NICHES = {
    "1": "tech",
    "2": "finance",
    "3": "health",
    "4": "ai",
}

# Facebook page category IDs
NICHE_CATEGORIES = {
    "tech":    2256,   # Computers & Internet
    "finance": 2200,   # Financial services
    "health":  2254,   # Health/Beauty
    "ai":      2256,   # Computers & Internet
}

NICHE_POST_TIMES = {
    "tech":    "18:00",
    "finance": "19:00",
    "health":  "20:00",
    "ai":      "21:00",
}


def load_pages() -> list:
    if os.path.exists(PAGES_FILE):
        with open(PAGES_FILE) as f:
            return json.load(f)
    return []


def save_pages(pages: list) -> None:
    with open(PAGES_FILE, "w") as f:
        json.dump(pages, f, indent=2)
    print(f"[PageCreator] pages.json updated ({len(pages)} pages total)")


def exchange_for_long_lived(short_token: str) -> str:
    """Exchange a short-lived token for a 60-day long-lived token."""
    r = requests.get(
        f"{FB_GRAPH}/oauth/access_token",
        params={
            "grant_type":        "fb_exchange_token",
            "client_id":         APP_ID,
            "client_secret":     APP_SECRET,
            "fb_exchange_token": short_token,
        },
        timeout=15,
    )
    data = r.json()
    if "access_token" in data:
        print("[PageCreator] Token exchanged for 60-day long-lived token.")
        return data["access_token"]
    print(f"[PageCreator] Token exchange failed: {data}. Using original token.")
    return short_token


def get_page_token(user_token: str, page_id: str) -> str:
    """Get the page-specific access token for a given page."""
    r = requests.get(
        f"{FB_GRAPH}/{page_id}",
        params={"fields": "access_token", "access_token": user_token},
        timeout=10,
    )
    data = r.json()
    return data.get("access_token", user_token)


def create_page_via_api(user_token: str, name: str, niche: str) -> dict | None:
    """Create a Facebook Page via the Graph API."""
    category = NICHE_CATEGORIES.get(niche, 2256)
    r = requests.post(
        f"{FB_GRAPH}/me/accounts",
        data={
            "name":          name,
            "category":      category,
            "access_token":  user_token,
        },
        timeout=15,
    )
    data = r.json()
    if "id" in data:
        print(f"[PageCreator] Page created! ID: {data['id']}")
        return data
    print(f"[PageCreator] API page creation failed: {data.get('error', {}).get('message', data)}")
    return None


def get_existing_pages(user_token: str) -> list:
    """Fetch all pages the user manages."""
    r = requests.get(
        f"{FB_GRAPH}/me/accounts",
        params={"access_token": user_token, "limit": 50},
        timeout=15,
    )
    data = r.json()
    return data.get("data", [])


def add_page_to_config(name: str, page_id: str, access_token: str, niche: str) -> bool:
    """Add a page to pages.json if it doesn't already exist."""
    pages = load_pages()
    existing_ids = {p["page_id"] for p in pages}

    if page_id in existing_ids:
        print(f"[PageCreator] Page {page_id} already in pages.json — skipping.")
        return False

    post_time = NICHE_POST_TIMES.get(niche, "18:00")

    # stagger post times to avoid overlap
    used_times = {p["post_time"] for p in pages}
    while post_time in used_times:
        h, m = post_time.split(":")
        post_time = f"{int(h)+1:02d}:{m}"

    pages.append({
        "name":         name,
        "page_id":      page_id,
        "access_token": access_token,
        "niche":        niche,
        "post_time":    post_time,
        "active":       True,
    })
    save_pages(pages)
    return True


def pick_niche() -> str:
    print("\nPick a niche:")
    for k, v in NICHES.items():
        print(f"  {k}. {v}")
    print("  5. custom (type your own)")
    choice = input("Choice [1-5]: ").strip()
    if choice in NICHES:
        return NICHES[choice]
    elif choice == "5":
        return input("Enter niche name: ").strip().lower()
    return "tech"


def run():
    print(f"\n{'='*55}")
    print(f"  FACEBOOK PAGE CREATOR")
    print(f"{'='*55}\n")

    print("You need a USER access token (not a page token).")
    print("Get one at: developers.facebook.com/tools/explorer")
    print("Click 'Get User Access Token' with these permissions:")
    print("  publish_video, pages_show_list, pages_read_engagement, pages_manage_posts\n")

    user_token = input("Paste your USER access token: ").strip()
    if not user_token:
        print("No token provided. Exiting.")
        sys.exit(1)

    # exchange for long-lived user token
    user_token = exchange_for_long_lived(user_token)

    print("\nHow do you want to add pages?")
    print("  1. Create a brand new page via API")
    print("  2. Import pages you already created on Facebook")
    mode = input("Choice [1/2]: ").strip()

    if mode == "2":
        # import existing pages
        print("\n[PageCreator] Fetching your existing Facebook pages...")
        fb_pages = get_existing_pages(user_token)
        if not fb_pages:
            print("No pages found. Make sure your token has pages_show_list permission.")
            sys.exit(1)

        print(f"\nFound {len(fb_pages)} page(s):\n")
        for i, p in enumerate(fb_pages, 1):
            print(f"  {i}. {p['name']} (ID: {p['id']})")

        print("\nFor each page, you'll pick a niche.\n")
        added = 0
        for p in fb_pages:
            print(f"\n--- {p['name']} ---")
            add = input("Add this page to automation? [y/n]: ").strip().lower()
            if add != "y":
                continue
            niche = pick_niche()
            page_token = exchange_for_long_lived(p.get("access_token", user_token))
            if add_page_to_config(p["name"], p["id"], page_token, niche):
                print(f"✅ {p['name']} added ({niche})")
                added += 1

        print(f"\n✅ Done! {added} page(s) added to pages.json.")

    else:
        # create new pages
        how_many = input("\nHow many new pages do you want to create? ").strip()
        try:
            count = int(how_many)
        except ValueError:
            count = 1

        added = 0
        for i in range(count):
            print(f"\n--- Page {i+1} of {count} ---")
            name  = input("Page name: ").strip()
            niche = pick_niche()

            print(f"\n[PageCreator] Creating '{name}' ({niche})...")
            result = create_page_via_api(user_token, name, niche)

            if result:
                page_id    = result["id"]
                page_token = get_page_token(user_token, page_id)
                page_token = exchange_for_long_lived(page_token)
                if add_page_to_config(name, page_id, page_token, niche):
                    print(f"✅ '{name}' created and added to pages.json")
                    added += 1
            else:
                print(f"⚠️  Could not create '{name}' via API.")
                print("   Create it manually on facebook.com then run this script again")
                print("   and choose option 2 (Import existing pages).")

        print(f"\n✅ Done! {added} page(s) created and added to pages.json.")

    print("\nNext step: push to Railway so the bot starts posting to all pages.")
    print(f"  git add pages.json && git push\n")


if __name__ == "__main__":
    run()
