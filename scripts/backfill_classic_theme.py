"""
Backfill classic-theme SVGs for existing birth charts.

Fetches all rows from user_birth_charts, filters to those missing
``chart_classic``, calls the RapidAPI with theme="classic", and patches
the chart_data JSONB column.

Idempotent: safe to re-run — rows that already have chart_classic are skipped.

Usage:
    uv run python scripts/backfill_classic_theme.py
"""

import asyncio
import logging
import os
import sys
from typing import Any, cast

import httpx
from dotenv import load_dotenv
from supabase import create_client

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DELAY_BETWEEN_CALLS = float(os.getenv("BACKFILL_DELAY", "1.0"))  # seconds

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY", "")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
RAPIDAPI_HOST = "astrologer.p.rapidapi.com"
BIRTH_CHART_ENDPOINT = f"https://{RAPIDAPI_HOST}/api/v5/chart/birth-chart"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fetch_all_charts() -> list[dict[str, Any]]:
    """Return all user_birth_charts rows (id, birth_data, chart_data)."""
    supabase = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)
    response = (
        supabase.table("user_birth_charts")
        .select("id,birth_data,chart_data")
        .execute()
    )
    return cast(list[dict[str, Any]], response.data or [])


def _needs_classic(chart: dict) -> bool:
    """True if the chart is missing or has an empty chart_classic."""
    chart_data = chart.get("chart_data") or {}
    classic = chart_data.get("chart_classic")
    return not classic


async def _generate_classic_svg(birth_data: dict) -> str:
    """Call RapidAPI with theme=classic and return the SVG string."""
    payload = {
        "subject": {
            "name": birth_data.get("name", ""),
            "year": birth_data["year"],
            "month": birth_data["month"],
            "day": birth_data["day"],
            "hour": birth_data["hour"],
            "minute": birth_data["minute"],
            "city": birth_data["city"],
            "nation": birth_data.get("nation") or birth_data.get("country", ""),
            "longitude": birth_data["longitude"],
            "latitude": birth_data["latitude"],
            "timezone": birth_data["timezone"],
            "zodiac_type": birth_data.get("zodiac_type", "Tropical"),
            "houses_system_identifier": birth_data.get("houses_system_identifier", "P"),
        },
        "theme": "classic",
        "language": "EN",
        "split_chart": False,
        "transparent_background": True,
        "show_house_position_comparison": True,
    }

    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(BIRTH_CHART_ENDPOINT, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data.get("chart", "")


def _update_chart_data(chart_id: str, chart_data: dict):
    """Patch the chart_data JSONB for a single row."""
    supabase = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)
    supabase.table("user_birth_charts").update(
        {"chart_data": chart_data}
    ).eq("id", chart_id).execute()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main():
    if not all([SUPABASE_URL, SUPABASE_SECRET_KEY, RAPIDAPI_KEY]):
        logger.error("Missing required env vars (SUPABASE_URL, SUPABASE_SECRET_KEY, RAPIDAPI_KEY)")
        sys.exit(1)

    all_charts = _fetch_all_charts()
    to_process = [c for c in all_charts if _needs_classic(c)]

    logger.info("Total charts: %d | Need classic SVG: %d", len(all_charts), len(to_process))

    if not to_process:
        logger.info("Nothing to do.")
        return

    success = 0
    failed = 0

    for idx, chart in enumerate(to_process, start=1):
        chart_id = chart["id"]
        birth_data = chart.get("birth_data") or {}

        try:
            classic_svg = await _generate_classic_svg(birth_data)
            if not classic_svg:
                logger.warning("[%d/%d] %s — API returned empty SVG, skipping", idx, len(to_process), chart_id)
                failed += 1
                continue

            updated_chart_data = {**(chart.get("chart_data") or {})}
            updated_chart_data["chart_classic"] = classic_svg
            _update_chart_data(chart_id, updated_chart_data)

            success += 1
            logger.info("[%d/%d] %s — OK", idx, len(to_process), chart_id)

        except Exception as exc:
            failed += 1
            logger.error("[%d/%d] %s — FAILED: %s", idx, len(to_process), chart_id, exc)

        if idx < len(to_process):
            await asyncio.sleep(DELAY_BETWEEN_CALLS)

    logger.info("Done. success=%d  failed=%d", success, failed)


if __name__ == "__main__":
    asyncio.run(main())
