"""
Export Supabase users to segmented CSV files for email campaigns.

Segments:
  HOT  — paid users OR free users with 2+ conversations
  WARM — users with a birth chart + exactly 1 conversation
  COLD — users who signed up but never used the app (0 charts, 0 conversations)

Usage:
    cd astrology-ai
    python scripts/export_users_for_email.py
"""

import csv
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = SCRIPT_DIR / "output"

# Your test account — excluded from all exports
EXCLUDED_EMAILS = {"petariliev@gmail.com", "ilievpetar24@gmail.com"}

load_dotenv(PROJECT_ROOT / ".env")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SECRET_KEY"]

CSV_COLUMNS = [
    "email",
    "name",
    "sun_sign",
    "moon_sign",
    "ascendant_sign",
    "segment",
    "plan",
    "conversation_count",
    "chart_count",
    "joined_date",
]


# ---------------------------------------------------------------------------
# Zodiac extraction (mirrors utils/chart_data_extractor.py logic)
# ---------------------------------------------------------------------------

def extract_zodiac(chart_data: dict | None) -> tuple[str, str, str]:
    """Return (sun_sign, moon_sign, ascendant_sign) from chart_data JSONB."""
    if not chart_data or not isinstance(chart_data, dict):
        return ("Unknown", "Unknown", "Unknown")

    # Navigate nested chart_data key
    data = chart_data
    if "chart_data" in data and isinstance(data["chart_data"], dict):
        data = data["chart_data"]

    subject = data.get("subject", {})
    if not isinstance(subject, dict):
        return ("Unknown", "Unknown", "Unknown")

    sun = subject.get("sun", {}).get("sign", "Unknown")
    moon = subject.get("moon", {}).get("sign", "Unknown")
    asc = subject.get("ascendant", {}).get("sign", "Unknown")
    return (sun, moon, asc)


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_all_users(supabase) -> list[dict]:
    """Fetch all auth users via admin API (handles pagination)."""
    users = []
    page = 1
    per_page = 100
    while True:
        response = supabase.auth.admin.list_users(page=page, per_page=per_page)
        batch = response if isinstance(response, list) else getattr(response, "users", [])
        if not batch:
            break
        users.extend(batch)
        if len(batch) < per_page:
            break
        page += 1
    return users


def fetch_table(supabase, table: str, columns: str = "*") -> list[dict]:
    """Fetch all rows from a Supabase table."""
    response = supabase.table(table).select(columns).execute()
    return response.data or []


# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------

def classify_segment(plan: str, conversation_count: int, chart_count: int) -> str:
    if plan in ("basic", "pro"):
        return "HOT"
    if conversation_count >= 2:
        return "HOT"
    if chart_count >= 1 and conversation_count >= 1:
        return "WARM"
    return "COLD"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Connecting to Supabase …")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    # 1. Fetch auth users
    print("Fetching users …")
    auth_users = fetch_all_users(supabase)
    print(f"  → {len(auth_users)} auth users")

    # 2. Fetch birth charts
    print("Fetching birth charts …")
    charts = fetch_table(supabase, "user_birth_charts", "user_id, chart_data, name")
    print(f"  → {len(charts)} birth charts")

    # Build lookup: user_id → list of charts
    charts_by_user: dict[str, list[dict]] = {}
    for c in charts:
        uid = c["user_id"]
        charts_by_user.setdefault(uid, []).append(c)

    # 3. Fetch subscriptions
    print("Fetching subscriptions …")
    subs = fetch_table(supabase, "user_subscriptions", "user_id, status")
    print(f"  → {len(subs)} subscriptions")

    subs_by_user: dict[str, str] = {}
    for s in subs:
        subs_by_user[s["user_id"]] = s["status"]

    # 4. Fetch conversations
    print("Fetching conversations …")
    convos = fetch_table(supabase, "chat_conversations", "user_id")
    print(f"  → {len(convos)} conversations")

    convo_count_by_user: dict[str, int] = {}
    for c in convos:
        uid = c["user_id"]
        convo_count_by_user[uid] = convo_count_by_user.get(uid, 0) + 1

    # 5. Build enriched rows
    print("Building user rows …")
    rows: list[dict] = []
    for user in auth_users:
        email = user.email if hasattr(user, "email") else user.get("email", "")
        if not email or email in EXCLUDED_EMAILS:
            continue

        uid = user.id if hasattr(user, "id") else user.get("id", "")
        uid = str(uid)

        # Name: from user metadata or first chart
        raw_meta = user.user_metadata if hasattr(user, "user_metadata") else user.get("user_metadata", {})
        name = (raw_meta or {}).get("full_name", "") or (raw_meta or {}).get("name", "")
        if not name:
            user_charts = charts_by_user.get(uid, [])
            if user_charts:
                name = user_charts[0].get("name", "")

        # Zodiac — take first chart
        user_charts = charts_by_user.get(uid, [])
        chart_count = len(user_charts)
        if user_charts:
            sun, moon, asc = extract_zodiac(user_charts[0].get("chart_data"))
        else:
            sun, moon, asc = ("Unknown", "Unknown", "Unknown")

        plan = subs_by_user.get(uid, "free")
        convo_count = convo_count_by_user.get(uid, 0)
        segment = classify_segment(plan, convo_count, chart_count)

        created = user.created_at if hasattr(user, "created_at") else user.get("created_at", "")
        if created:
            try:
                joined = datetime.fromisoformat(str(created).replace("Z", "+00:00")).strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                joined = str(created)[:10]
        else:
            joined = ""

        rows.append({
            "email": email,
            "name": name,
            "sun_sign": sun,
            "moon_sign": moon,
            "ascendant_sign": asc,
            "segment": segment,
            "plan": plan,
            "conversation_count": convo_count,
            "chart_count": chart_count,
            "joined_date": joined,
        })

    # 6. Write CSVs
    def write_csv(filename: str, data: list[dict]) -> None:
        path = OUTPUT_DIR / filename
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(data)
        print(f"  ✓ {path.name}: {len(data)} rows")

    hot = [r for r in rows if r["segment"] == "HOT"]
    warm = [r for r in rows if r["segment"] == "WARM"]
    cold = [r for r in rows if r["segment"] == "COLD"]

    print(f"\nSegmentation: {len(hot)} HOT, {len(warm)} WARM, {len(cold)} COLD ({len(rows)} total)")
    print("Writing CSVs …")
    write_csv("all_users.csv", rows)
    write_csv("hot_users.csv", hot)
    write_csv("warm_users.csv", warm)
    write_csv("cold_users.csv", cold)

    print("\nDone! Files in:", OUTPUT_DIR)


if __name__ == "__main__":
    main()
