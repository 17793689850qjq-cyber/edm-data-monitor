#!/usr/bin/env python3
"""Add engagement comparison groups to dashboard JSON without replacing GMV/conv MoM/YoY."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from comparisons import build_comparisons, seed_comparison_snapshots
from klaviyo_config import comparison_periods
from sync_dashboard import totals_from_rows

ENGAGEMENT_KEYS = ("engagementTotals", "engagementCampaign", "engagementFlow")


def merge_engagement(existing: dict, fresh: dict) -> None:
    for key in ENGAGEMENT_KEYS:
        if key in fresh:
            existing[key] = fresh[key]


def rebuild(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    period = data["meta"]["period"]
    rows = data["rows"]
    totals = data.get("totals") or totals_from_rows(rows)
    comparisons = data.get("comparisons") or {}

    ranges = comparison_periods(period)
    mom_totals, mom_rows, yoy_totals, yoy_rows = seed_comparison_snapshots(rows, totals)
    fresh = build_comparisons(
        totals,
        mom_totals,
        yoy_totals,
        rows,
        mom_rows,
        yoy_rows,
        period_meta=period,
        mom_period=ranges.get("mom") or comparisons.get("meta", {}).get("mom"),
        yoy_period=ranges.get("yoy") or comparisons.get("meta", {}).get("yoy"),
    )

    if "global" not in comparisons:
        comparisons = fresh
    else:
        merge_engagement(comparisons["global"], fresh["global"])
        for code, site_block in fresh.get("sites", {}).items():
            comparisons.setdefault("sites", {}).setdefault(code, {})
            merge_engagement(comparisons["sites"][code], site_block)

    data["comparisons"] = comparisons
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Merged engagement comparisons into {path}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", type=Path, default=[ROOT / "dashboard" / "data" / "dashboard-30d.json"])
    args = ap.parse_args()
    for p in args.paths:
        rebuild(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
