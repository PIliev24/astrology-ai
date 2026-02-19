"""
Setup script for AIstrology email campaigns.

Automates creation of templates, campaigns, sequences, and recipient imports
by calling the deployed email-automator backend API and Supabase REST API.

Usage:
    uv run python scripts/setup_email_campaigns.py

Prerequisites:
    - email-automator backend deployed at Railway
    - Mailjet credentials already configured in the system
    - CSV user exports in scripts/output/
    - Email templates in scripts/email_templates/
"""

import asyncio
import csv
import io
import re
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

# ==================== Configuration ====================

# Load Supabase credentials from email-automator .env
_email_automator_env = Path(__file__).resolve().parent.parent.parent / "email-automator" / ".env"
load_dotenv(_email_automator_env)

import os

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SECRET_KEY = os.environ["SUPABASE_SECRET_KEY"]

BACKEND_URL = "https://email-automator-production-7534.up.railway.app"
USER_ID = "7bee016e-c34a-49f9-ad66-8d23877d711c"

SCRIPTS_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = SCRIPTS_DIR / "email_templates"
OUTPUT_DIR = SCRIPTS_DIR / "output"

# Zodiac abbreviation → Bulgarian name mapping
ZODIAC_MAP = {
    "Ari": "Овен",
    "Tau": "Телец",
    "Gem": "Близнаци",
    "Can": "Рак",
    "Leo": "Лъв",
    "Vir": "Дева",
    "Lib": "Везни",
    "Sco": "Скорпион",
    "Sag": "Стрелец",
    "Cap": "Козирог",
    "Aqu": "Водолей",
    "Pis": "Риби",
}


# ==================== Markdown → HTML Conversion ====================


def md_to_html(text: str) -> str:
    """Convert markdown body text to HTML suitable for email.

    Handles: bold, italic, links, blockquotes, ordered lists, and line breaks.
    Wraps output in <div> so email_sending_service detects it as HTML.
    """
    lines = text.split("\n")
    html_lines: list[str] = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        # Blank line
        if not stripped:
            if in_list:
                html_lines.append("</ol>")
                in_list = False
            html_lines.append("<br>")
            continue

        # Blockquote
        if stripped.startswith(">"):
            content = stripped.lstrip("> ").strip()
            content = _inline_md(content)
            if in_list:
                html_lines.append("</ol>")
                in_list = False
            html_lines.append(f"<blockquote>{content}</blockquote>")
            continue

        # Ordered list item (1. item, 2. item, etc.)
        ol_match = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if ol_match:
            if not in_list:
                html_lines.append("<ol>")
                in_list = True
            content = _inline_md(ol_match.group(2))
            html_lines.append(f"<li>{content}</li>")
            continue

        # Unordered list item (- item)
        ul_match = re.match(r"^[-*]\s+(.+)$", stripped)
        if ul_match:
            if in_list:
                html_lines.append("</ol>")
                in_list = False
            content = _inline_md(ul_match.group(1))
            html_lines.append(f"&bull; {content}<br>")
            continue

        # Markdown table → simple HTML table
        if stripped.startswith("|"):
            if in_list:
                html_lines.append("</ol>")
                in_list = False
            # Skip separator rows like |------|------|
            if re.match(r"^\|[-|\s:]+\|$", stripped):
                continue
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            row_html = "".join(f"<td style='padding:4px 12px;'>{_inline_md(c)}</td>" for c in cells)
            html_lines.append(f"<tr>{row_html}</tr>")
            continue

        # Regular paragraph
        if in_list:
            html_lines.append("</ol>")
            in_list = False
        content = _inline_md(stripped)
        html_lines.append(f"{content}<br>")

    if in_list:
        html_lines.append("</ol>")

    # Wrap tables in <table> tags
    result = "\n".join(html_lines)
    if "<tr>" in result:
        result = result.replace(
            "<tr>",
            "<table style='border-collapse:collapse;'><tr>",
            1,  # only first occurrence gets the opening tag
        )
        # Find the last </tr> and add closing </table>
        last_tr = result.rfind("</tr>")
        if last_tr != -1:
            result = result[: last_tr + 5] + "</table>" + result[last_tr + 5 :]

    return f"<div>{result}</div>"


def _inline_md(text: str) -> str:
    """Convert inline markdown: bold, italic, links."""
    # Links: [text](url)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    # Bold: **text**
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    # Italic: *text*
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
    return text


# ==================== Template Parsing ====================


def parse_template(filepath: Path) -> dict[str, str]:
    """Parse a markdown email template file.

    Extracts subject and body from the template format:
    - Subject line starts with **Subject:**
    - Body is between the second --- and the final --- footer
    """
    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")

    subject = ""
    body_lines: list[str] = []
    separator_count = 0
    in_body = False
    footer_started = False

    for line in lines:
        stripped = line.strip()

        # Extract subject
        if stripped.startswith("**Subject:**"):
            subject = stripped.replace("**Subject:**", "").strip()
            continue

        # Track --- separators
        if stripped == "---":
            separator_count += 1
            if separator_count == 2:
                in_body = True
                continue
            if separator_count >= 3 and in_body:
                footer_started = True
                continue

        if in_body and not footer_started:
            body_lines.append(line)

    # Trim leading/trailing blank lines from body
    body_text = "\n".join(body_lines).strip()

    # Convert markdown body to HTML
    html_body = md_to_html(body_text)

    return {
        "name": filepath.stem,
        "subject": subject,
        "body": html_body,
    }


# ==================== CSV Preprocessing ====================


def preprocess_csv(input_path: Path) -> str:
    """Read a user CSV, expand zodiac abbreviations, and return import-ready CSV string.

    Output columns: email, name, company, sun_sign, moon_sign, ascendant_sign
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["email", "name", "company", "sun_sign", "moon_sign", "ascendant_sign"])

    with open(input_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            email = row["email"].strip()
            name = row.get("name", "").strip()
            sun = ZODIAC_MAP.get(row.get("sun_sign", "").strip(), "")
            moon = ZODIAC_MAP.get(row.get("moon_sign", "").strip(), "")
            asc = ZODIAC_MAP.get(row.get("ascendant_sign", "").strip(), "")

            # Replace "Unknown" → empty
            if row.get("sun_sign", "").strip() == "Unknown":
                sun = ""
            if row.get("moon_sign", "").strip() == "Unknown":
                moon = ""
            if row.get("ascendant_sign", "").strip() == "Unknown":
                asc = ""

            writer.writerow([email, name, "", sun, moon, asc])

    return output.getvalue()


# ==================== API Helpers ====================


def supabase_headers() -> dict[str, str]:
    return {
        "apikey": SUPABASE_SECRET_KEY,
        "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def api_params(**kwargs: Any) -> dict[str, Any]:
    """Build query params with user_id always included."""
    return {"user_id": USER_ID, **kwargs}


# ==================== Main Setup Logic ====================


async def create_templates(client: httpx.AsyncClient) -> dict[str, str]:
    """Create all 8 email templates via Supabase REST API.

    Returns: mapping of template filename stem → template UUID
    """
    template_files = sorted(TEMPLATES_DIR.glob("*.md"))
    template_ids: dict[str, str] = {}

    print(f"\n{'='*60}")
    print("STEP 1: Creating {0} email templates...".format(len(template_files)))
    print(f"{'='*60}")

    for tf in template_files:
        parsed = parse_template(tf)

        res = await client.post(
            f"{SUPABASE_URL}/rest/v1/email_templates",
            headers=supabase_headers(),
            json={
                "user_id": USER_ID,
                "name": parsed["name"],
                "subject": parsed["subject"],
                "body": parsed["body"],
            },
        )

        if res.status_code not in (200, 201):
            print(f"  ERROR creating template '{parsed['name']}': {res.status_code} - {res.text}")
            continue

        data = res.json()
        template_id = data[0]["id"] if isinstance(data, list) else data["id"]
        template_ids[parsed["name"]] = template_id
        print(f"  + {parsed['name']}: {template_id}")

    print(f"\nCreated {len(template_ids)}/{len(template_files)} templates")
    return template_ids


async def get_credential_id(client: httpx.AsyncClient) -> str:
    """Fetch the existing Mailjet credential ID."""
    print(f"\n{'='*60}")
    print("STEP 2: Fetching email credential...")
    print(f"{'='*60}")

    res = await client.get(
        f"{BACKEND_URL}/api/email-provider/credentials",
        params=api_params(),
    )

    if res.status_code != 200:
        raise RuntimeError(f"Failed to fetch credentials: {res.status_code} - {res.text}")

    credentials = res.json().get("credentials", [])
    if not credentials:
        raise RuntimeError("No email credentials found. Configure Mailjet in the frontend first.")

    cred = credentials[0]
    cred_id = cred["id"]
    print(f"  Found credential: {cred.get('name', 'N/A')} ({cred.get('from_email', 'N/A')}) → {cred_id}")
    return cred_id


async def create_campaigns(
    client: httpx.AsyncClient,
    credential_id: str,
) -> dict[str, str]:
    """Create 3 campaigns. Returns mapping of campaign key → campaign UUID."""
    print(f"\n{'='*60}")
    print("STEP 3: Creating campaigns...")
    print(f"{'='*60}")

    campaigns_config = [
        {
            "key": "warm",
            "name": "AIstrology — WARM Drip",
            "description": "6-email drip sequence for warm users (have birth chart + 1 conversation)",
            "funnel_stage": "warm",
            "daily_limit": 30,
            "hourly_limit": 15,
        },
        {
            "key": "cold",
            "name": "AIstrology — COLD Re-engagement",
            "description": "Single re-engagement email for cold users (registered but never used)",
            "funnel_stage": "broad",
            "daily_limit": 10,
            "hourly_limit": 10,
        },
        {
            "key": "hot",
            "name": "AIstrology — HOT Personal",
            "description": "Personal feedback request for most engaged users",
            "funnel_stage": "hot",
            "daily_limit": 10,
            "hourly_limit": 10,
        },
    ]

    campaign_ids: dict[str, str] = {}

    for cfg in campaigns_config:
        res = await client.post(
            f"{BACKEND_URL}/api/campaigns",
            params=api_params(),
            json={
                "name": cfg["name"],
                "description": cfg["description"],
                "funnel_stage": cfg["funnel_stage"],
                "email_credential_id": credential_id,
                "daily_limit": cfg["daily_limit"],
                "hourly_limit": cfg["hourly_limit"],
                "send_window_start": "09:00",
                "send_window_end": "20:00",
            },
        )

        if res.status_code not in (200, 201):
            print(f"  ERROR creating campaign '{cfg['name']}': {res.status_code} - {res.text}")
            continue

        data = res.json()
        campaign = data.get("campaign", data)
        campaign_id = campaign["id"]
        campaign_ids[cfg["key"]] = campaign_id
        print(f"  + {cfg['name']}: {campaign_id}")

    print(f"\nCreated {len(campaign_ids)}/3 campaigns")
    return campaign_ids


async def create_sequences(
    client: httpx.AsyncClient,
    campaign_ids: dict[str, str],
    template_ids: dict[str, str],
) -> None:
    """Create sequence steps for each campaign."""
    print(f"\n{'='*60}")
    print("STEP 4: Creating sequences...")
    print(f"{'='*60}")

    # WARM campaign sequences
    warm_sequences = [
        {"order": 0, "template": "01_welcome", "delay": 0, "condition": "always", "vary": False, "name": "Welcome"},
        {"order": 1, "template": "02_value_demo", "delay": 3, "condition": "always", "vary": False, "name": "Value Demo"},
        {"order": 2, "template": "03_social_proof", "delay": 3, "condition": "always", "vary": False, "name": "Social Proof"},
        {"order": 3, "template": "04_feature_showcase", "delay": 2, "condition": "no_reply", "vary": False, "name": "Feature Showcase"},
        {"order": 4, "template": "05_objection_handling", "delay": 3, "condition": "no_reply", "vary": False, "name": "Objection Handling"},
        {"order": 5, "template": "06_final_offer", "delay": 3, "condition": "no_reply", "vary": False, "name": "Final Offer"},
    ]

    cold_sequences = [
        {
            "order": 0,
            "template": "cold_reengagement",
            "delay": 0,
            "condition": "always",
            "vary": True,
            "name": "Re-engagement",
            "personalization": (
                "This email is in Bulgarian. If any {name} placeholder remains unfilled, "
                "replace it with nothing — just use the greeting 'Здравей!' without a name. "
                "Do NOT translate or rewrite any other Bulgarian text."
            ),
        },
    ]

    hot_sequences = [
        {"order": 0, "template": "hot_personal", "delay": 0, "condition": "always", "vary": False, "name": "Personal Feedback"},
    ]

    sequence_map = {
        "warm": warm_sequences,
        "cold": cold_sequences,
        "hot": hot_sequences,
    }

    for campaign_key, sequences in sequence_map.items():
        campaign_id = campaign_ids.get(campaign_key)
        if not campaign_id:
            print(f"  SKIP {campaign_key} — no campaign ID")
            continue

        print(f"\n  [{campaign_key.upper()} campaign]")

        for seq in sequences:
            tmpl_id = template_ids.get(seq["template"])
            if not tmpl_id:
                print(f"    ERROR: Template '{seq['template']}' not found")
                continue

            body: dict[str, Any] = {
                "name": seq["name"],
                "sequence_order": seq["order"],
                "template_id": tmpl_id,
                "delay_days": seq["delay"],
                "delay_hours": 0,
                "condition_type": seq["condition"],
                "vary_text": seq["vary"],
            }

            if seq.get("personalization"):
                body["personalization_instructions"] = seq["personalization"]

            res = await client.post(
                f"{BACKEND_URL}/api/campaigns/{campaign_id}/sequences",
                params=api_params(),
                json=body,
            )

            if res.status_code not in (200, 201):
                print(f"    ERROR creating sequence '{seq['name']}': {res.status_code} - {res.text}")
                continue

            data = res.json()
            seq_data = data.get("sequence", data)
            print(f"    + Step {seq['order']}: {seq['name']} (delay={seq['delay']}d, condition={seq['condition']}) → {seq_data['id']}")


async def import_recipients(
    client: httpx.AsyncClient,
    campaign_ids: dict[str, str],
) -> None:
    """Preprocess CSVs and import recipients into each campaign."""
    print(f"\n{'='*60}")
    print("STEP 5: Importing recipients...")
    print(f"{'='*60}")

    imports = [
        ("warm", OUTPUT_DIR / "warm_users.csv"),
        ("cold", OUTPUT_DIR / "cold_users.csv"),
        ("hot", OUTPUT_DIR / "hot_users.csv"),
    ]

    for campaign_key, csv_path in imports:
        campaign_id = campaign_ids.get(campaign_key)
        if not campaign_id:
            print(f"  SKIP {campaign_key} — no campaign ID")
            continue

        if not csv_path.exists():
            print(f"  SKIP {campaign_key} — CSV not found: {csv_path}")
            continue

        csv_content = preprocess_csv(csv_path)

        # Upload as multipart file
        res = await client.post(
            f"{BACKEND_URL}/api/campaigns/{campaign_id}/recipients/import",
            params=api_params(),
            files={"file": (f"{campaign_key}_users.csv", csv_content.encode("utf-8"), "text/csv")},
        )

        if res.status_code not in (200, 201):
            print(f"  ERROR importing {campaign_key}: {res.status_code} - {res.text}")
            continue

        result = res.json()
        imported = result.get("imported_count", 0)
        errors = result.get("error_count", 0)
        print(f"  + {campaign_key.upper()}: {imported} imported, {errors} errors")

        if result.get("errors"):
            for err in result["errors"]:
                print(f"    ! {err}")


def print_summary(
    template_ids: dict[str, str],
    campaign_ids: dict[str, str],
    credential_id: str,
) -> None:
    """Print final summary and review checklist."""
    print(f"\n{'='*60}")
    print("SETUP COMPLETE")
    print(f"{'='*60}")

    print(f"\nBackend: {BACKEND_URL}")
    print(f"Frontend: https://email-automator-fe.vercel.app/")
    print(f"User ID: {USER_ID}")
    print(f"Credential: {credential_id}")

    print(f"\nTemplates ({len(template_ids)}):")
    for name, tid in template_ids.items():
        print(f"  {name}: {tid}")

    print(f"\nCampaigns ({len(campaign_ids)}):")
    for key, cid in campaign_ids.items():
        print(f"  {key}: {cid}")
        print(f"    View: https://email-automator-fe.vercel.app/campaigns/{cid}")

    print(f"\n{'='*60}")
    print("REVIEW CHECKLIST")
    print(f"{'='*60}")
    print("""
1. Verify templates at: https://email-automator-fe.vercel.app/templates
   - Check all 8 templates have correct HTML formatting
   - Verify {name}, {sun_sign}, {moon_sign}, {ascendant_sign} placeholders are intact

2. Verify campaigns at: https://email-automator-fe.vercel.app/campaigns
   - Each campaign should have the correct sequences and recipients

3. Send a test email from: https://email-automator-fe.vercel.app/email-accounts
   - Verify email arrives with correct formatting

4. EXECUTION ORDER:
   Phase 1 (Day 0): Start HOT campaign → review 6 personal emails
   Phase 2 (Day 1): Start WARM campaign → 29 welcome emails go out
   Phase 3 (Day 3): Start COLD campaign → 4 re-engagement emails

NOTE: No campaigns have been activated. Start them manually via the frontend.
""")


async def main() -> None:
    print("AIstrology Email Campaign Setup")
    print(f"Backend: {BACKEND_URL}")
    print(f"Supabase: {SUPABASE_URL}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Create templates
        template_ids = await create_templates(client)

        # Step 2: Get credential ID
        credential_id = await get_credential_id(client)

        # Step 3: Create campaigns
        campaign_ids = await create_campaigns(client, credential_id)

        # Step 4: Create sequences
        await create_sequences(client, campaign_ids, template_ids)

        # Step 5: Import recipients
        await import_recipients(client, campaign_ids)

        # Summary
        print_summary(template_ids, campaign_ids, credential_id)


if __name__ == "__main__":
    asyncio.run(main())
