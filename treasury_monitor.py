"""
treasury_monitor.py — US Treasury auction monitor for GitHub Actions.

Automatically selects the most recent auction date from auction_schedule.py.
No manual date input needed — just run it.

Run:
    python treasury_monitor.py              # auto date
    python treasury_monitor.py --preview    # send upcoming schedule to Discord
    python treasury_monitor.py --force      # alert even if data unchanged
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

from auction_schedule import (
    get_scheduled,
    most_recent_auction_date,
    upcoming_auctions,
)

TREASURY_API  = "https://www.treasurydirect.gov/TA_WS/securities/search"
CURRENT_FILE  = Path("treasury_current.json")
PREVIOUS_FILE = Path("treasury_previous.json")

TYPE_EMOJI = {"BILL": "💵", "NOTE": "📄", "BOND": "🏛️", "TIPS": "📊", "FRN": "🔄"}


# ── Fetch ──────────────────────────────────────────────────────────────────

def fetch_auctions(auction_date: str) -> list[dict]:
    scheduled = get_scheduled(auction_date)
    sec_types = list(dict.fromkeys(t for _, t in scheduled))
    results = []
    for sec_type in sec_types:
        try:
            resp = requests.get(
                TREASURY_API,
                params={"startDate": auction_date, "endDate": auction_date, "type": sec_type},
                headers={"User-Agent": "TreasuryMonitor/1.0"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                results.extend(data)
                print(f"  Fetched {len(data)} {sec_type}(s)")
            elif isinstance(data, dict) and data:
                results.append(data)
                print(f"  Fetched 1 {sec_type}")
        except Exception as e:
            print(f"  Error {sec_type}: {e}")
    return results


# ── Parse ──────────────────────────────────────────────────────────────────

def _f(v) -> float:
    try:
        return float(v) if v not in (None, "", "null") else 0.0
    except (ValueError, TypeError):
        return 0.0

def _pct(part: float, whole: float) -> float:
    return round(part / whole * 100, 1) if whole > 0 else 0.0

def parse_auction(raw: dict) -> dict:
    term     = raw.get("securityTerm", raw.get("term", "Unknown"))
    sec_type = raw.get("securityType", raw.get("type", ""))
    offering       = _f(raw.get("offeringAmount"))
    total_tendered = _f(raw.get("totalTendered"))
    total_accepted = _f(raw.get("totalAccepted"))
    direct_acc     = _f(raw.get("directBidderAccepted"))
    indirect_acc   = _f(raw.get("indirectBidderAccepted"))
    dealer_acc     = _f(raw.get("primaryDealerAccepted"))
    high_rate      = _f(raw.get("highDiscountRate") or raw.get("highYield"))
    btc            = _f(raw.get("bidToCoverRatio"))
    return {
        "label":            f"{term} {sec_type}",
        "security_term":    term,
        "security_type":    sec_type,
        "auction_date":     raw.get("auctionDate", ""),
        "issue_date":       raw.get("issueDate", ""),
        "offering_m":       offering,
        "total_tendered_m": total_tendered,
        "total_accepted_m": total_accepted,
        "bid_to_cover":     btc,
        "high_rate_pct":    high_rate,
        "direct":   {"accepted_m": direct_acc,  "pct": _pct(direct_acc,  total_accepted)},
        "indirect": {"accepted_m": indirect_acc, "pct": _pct(indirect_acc, total_accepted)},
        "dealer":   {"accepted_m": dealer_acc,   "pct": _pct(dealer_acc,   total_accepted)},
    }


# ── Persistence ────────────────────────────────────────────────────────────

def _load(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {}

def _hash(auctions: list) -> str:
    return hashlib.sha256(json.dumps(auctions, sort_keys=True).encode()).hexdigest()

def rotate_and_save(dataset: dict) -> bool:
    current = _load(CURRENT_FILE)
    changed = _hash(dataset.get("auctions", [])) != _hash(current.get("auctions", []))
    if changed and current:
        PREVIOUS_FILE.write_text(json.dumps(current, indent=2))
        print(f"Rotated → {PREVIOUS_FILE}")
    CURRENT_FILE.write_text(json.dumps(dataset, indent=2))
    print(f"Saved   → {CURRENT_FILE}")
    return changed


# ── Formatting ─────────────────────────────────────────────────────────────

def fmt(v: float) -> str:
    return f"${v/1000:.2f}B" if v >= 1000 else f"${v:.0f}M"

def btc_label(btc: float) -> str:
    if btc >= 2.5: return "🟢 Strong"
    if btc >= 2.0: return "🟡 Average"
    if btc > 0:    return "🔴 Weak"
    return "⏳ Pending"


# ── Discord ────────────────────────────────────────────────────────────────

def send_discord_results(auctions: list[dict], auction_date: str, upcoming: list) -> None:
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("No DISCORD_WEBHOOK_URL — skipping.")
        return
    fields = []
    for a in auctions:
        emoji = TYPE_EMOJI.get(a["security_type"], "📋")
        btc   = a["bid_to_cover"]
        value = (
            f"**Offered:** {fmt(a['offering_m'])}  "
            f"**Tendered:** {fmt(a['total_tendered_m'])}\n"
            f"**Bid-to-Cover:** `{btc:.2f}x`  {btc_label(btc)}\n"
            f"**High Rate:** `{a['high_rate_pct']:.3f}%`\n\n"
            f"**Buyer Breakdown** *(% of accepted)*\n"
            f"🏛️ Direct:             {fmt(a['direct']['accepted_m'])}  `{a['direct']['pct']}%`\n"
            f"🌍 Indirect / Foreign: {fmt(a['indirect']['accepted_m'])}  `{a['indirect']['pct']}%`\n"
            f"🏦 Primary Dealer:     {fmt(a['dealer']['accepted_m'])}  `{a['dealer']['pct']}%`"
        )
        fields.append({"name": f"{emoji} {a['label']}", "value": value, "inline": False})
    if upcoming:
        lines = []
        for d, items in upcoming[:3]:
            day = datetime.strptime(d, "%Y-%m-%d").strftime("%a %b %d")
            lines.append(f"**{day}:** {', '.join(f'{t} {s}' for t,s in items)}")
        fields.append({"name": "📅 Coming Up", "value": "\n".join(lines), "inline": False})
    embed = {
        "title": f"🏛️ US Treasury Auction Results — {auction_date}",
        "color": 0x1E90FF,
        "fields": fields,
        "footer": {"text": f"TreasuryDirect  •  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"},
    }
    resp = requests.post(webhook_url, json={"embeds": [embed]}, timeout=10)
    resp.raise_for_status()
    print(f"Discord sent — {len(auctions)} auction(s).")


def send_discord_preview(upcoming: list, today: str) -> None:
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return
    fields = []
    for d, items in upcoming:
        day = datetime.strptime(d, "%Y-%m-%d").strftime("%A, %B %d")
        lines = [f"{TYPE_EMOJI.get(s,'📋')} {term} {s}" for term, s in items]
        fields.append({"name": day, "value": "\n".join(lines), "inline": True})
    embed = {
        "title": f"📅 Treasury Auction Schedule — Week of {today}",
        "color": 0x1E90FF,
        "fields": fields,
        "footer": {"text": "Source: US Treasury Tentative Auction Schedule"},
    }
    resp = requests.post(webhook_url, json={"embeds": [embed]}, timeout=10)
    resp.raise_for_status()
    print("Discord preview sent.")


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force",   action="store_true")
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()

    today = datetime.now(timezone.utc).date().isoformat()
    upcoming = upcoming_auctions(from_date=today, days=4)

    if args.preview:
        send_discord_preview(upcoming, today)
        return

    # Auto-select — no date input needed
    auction_date = most_recent_auction_date()
    if not auction_date:
        print("No scheduled auction dates found in the past 7 days.")
        sys.exit(0)

    scheduled = get_scheduled(auction_date)
    print(f"Auto-selected: {auction_date}")
    print(f"Scheduled:     {', '.join(f'{t} {s}' for t,s in scheduled)}")

    raw = fetch_auctions(auction_date)
    if not raw:
        print("No results yet — auction results post after 1:00 PM ET.")
        sys.exit(0)

    parsed = [parse_auction(r) for r in raw]

    for a in parsed:
        print(f"  {a['label']}: BTC {a['bid_to_cover']:.2f}x | Rate {a['high_rate_pct']:.3f}% | "
              f"Direct {a['direct']['pct']}% Indirect {a['indirect']['pct']}% Dealer {a['dealer']['pct']}%")

    dataset = {
        "fetched_at":   datetime.now(timezone.utc).isoformat(),
        "auction_date": auction_date,
        "scheduled":    scheduled,
        "auctions":     parsed,
    }

    changed = rotate_and_save(dataset)

    if changed or args.force:
        print("Data changed — alerting Discord.")
        send_discord_results(parsed, auction_date, upcoming)
    else:
        print("Unchanged — no alert sent.")


if __name__ == "__main__":
    main()
