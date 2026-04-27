"""
treasury_monitor.py — US Treasury auction monitor for GitHub Actions.

Uses the official tentative auction schedule (Feb–Aug 2026) to:
- Know what's auctioning on any given day
- Fetch results from TreasuryDirect after 1PM ET cutoff
- Show buyer breakdown: direct / indirect(foreign) / primary dealer
- Retain last 2 datasets, only alert Discord if data changed
- Preview upcoming auctions for the next 3 days

Run:
    python treasury_monitor.py                  # today
    python treasury_monitor.py --date 2026-04-24  # specific date
    python treasury_monitor.py --preview        # show upcoming schedule only
    python treasury_monitor.py --force          # alert even if unchanged
"""

import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

# ── Official Auction Schedule (Feb–Aug 2026) ──────────────────────────────
# Source: US Treasury Tentative Auction Schedule PDF

_RAW_SCHEDULE = """
2026-02-09,BILL,13-Week
2026-02-09,BILL,26-Week
2026-02-10,BILL,6-Week
2026-02-10,NOTE,3-Year
2026-02-11,NOTE,10-Year
2026-02-11,BILL,17-Week
2026-02-12,BOND,30-Year
2026-02-12,BILL,4-Week
2026-02-12,BILL,8-Week
2026-02-17,BILL,6-Week
2026-02-17,BILL,13-Week
2026-02-17,BILL,26-Week
2026-02-17,BILL,52-Week
2026-02-18,BOND,20-Year
2026-02-18,BILL,17-Week
2026-02-19,BILL,4-Week
2026-02-19,BILL,8-Week
2026-02-19,TIPS,30-Year
2026-02-23,BILL,13-Week
2026-02-23,BILL,26-Week
2026-02-24,BILL,6-Week
2026-02-24,NOTE,2-Year
2026-02-25,FRN,2-Year
2026-02-25,NOTE,5-Year
2026-02-25,BILL,17-Week
2026-02-26,NOTE,7-Year
2026-02-26,BILL,4-Week
2026-02-26,BILL,8-Week
2026-03-02,BILL,13-Week
2026-03-02,BILL,26-Week
2026-03-03,BILL,6-Week
2026-03-04,BILL,17-Week
2026-03-05,BILL,4-Week
2026-03-05,BILL,8-Week
2026-03-09,BILL,13-Week
2026-03-09,BILL,26-Week
2026-03-10,BILL,6-Week
2026-03-10,NOTE,3-Year
2026-03-11,NOTE,10-Year
2026-03-11,BILL,17-Week
2026-03-12,BOND,30-Year
2026-03-12,BILL,4-Week
2026-03-12,BILL,8-Week
2026-03-16,BILL,13-Week
2026-03-16,BILL,26-Week
2026-03-17,BILL,6-Week
2026-03-17,BILL,52-Week
2026-03-17,BOND,20-Year
2026-03-18,BILL,17-Week
2026-03-19,BILL,4-Week
2026-03-19,BILL,8-Week
2026-03-19,TIPS,10-Year
2026-03-23,BILL,13-Week
2026-03-23,BILL,26-Week
2026-03-24,BILL,6-Week
2026-03-24,NOTE,2-Year
2026-03-25,FRN,2-Year
2026-03-25,NOTE,5-Year
2026-03-25,BILL,17-Week
2026-03-26,NOTE,7-Year
2026-03-26,BILL,4-Week
2026-03-26,BILL,8-Week
2026-03-30,BILL,13-Week
2026-03-30,BILL,26-Week
2026-03-31,BILL,6-Week
2026-04-01,BILL,17-Week
2026-04-02,BILL,4-Week
2026-04-02,BILL,8-Week
2026-04-06,BILL,13-Week
2026-04-06,BILL,26-Week
2026-04-07,BILL,6-Week
2026-04-07,NOTE,3-Year
2026-04-08,NOTE,10-Year
2026-04-08,BILL,17-Week
2026-04-09,BOND,30-Year
2026-04-09,BILL,4-Week
2026-04-09,BILL,8-Week
2026-04-13,BILL,13-Week
2026-04-13,BILL,26-Week
2026-04-14,BILL,6-Week
2026-04-14,BILL,52-Week
2026-04-15,BILL,17-Week
2026-04-16,BILL,4-Week
2026-04-16,BILL,8-Week
2026-04-20,BILL,13-Week
2026-04-20,BILL,26-Week
2026-04-21,BILL,6-Week
2026-04-22,BOND,20-Year
2026-04-22,BILL,17-Week
2026-04-23,BILL,4-Week
2026-04-23,BILL,8-Week
2026-04-23,TIPS,5-Year
2026-04-27,BILL,13-Week
2026-04-27,BILL,26-Week
2026-04-27,NOTE,2-Year
2026-04-27,NOTE,5-Year
2026-04-28,BILL,6-Week
2026-04-28,FRN,2-Year
2026-04-28,NOTE,7-Year
2026-04-29,BILL,17-Week
2026-04-30,BILL,4-Week
2026-04-30,BILL,8-Week
2026-05-04,BILL,13-Week
2026-05-04,BILL,26-Week
2026-05-05,BILL,6-Week
2026-05-06,BILL,17-Week
2026-05-07,BILL,4-Week
2026-05-07,BILL,8-Week
2026-05-11,BILL,13-Week
2026-05-11,BILL,26-Week
2026-05-11,NOTE,3-Year
2026-05-12,NOTE,10-Year
2026-05-12,BILL,6-Week
2026-05-12,BILL,52-Week
2026-05-13,BOND,30-Year
2026-05-13,BILL,17-Week
2026-05-14,BILL,4-Week
2026-05-14,BILL,8-Week
2026-05-18,BILL,13-Week
2026-05-18,BILL,26-Week
2026-05-19,BILL,6-Week
2026-05-20,BOND,20-Year
2026-05-20,BILL,17-Week
2026-05-21,BILL,4-Week
2026-05-21,BILL,8-Week
2026-05-21,TIPS,10-Year
2026-05-26,BILL,6-Week
2026-05-26,BILL,13-Week
2026-05-26,BILL,26-Week
2026-05-26,NOTE,2-Year
2026-05-27,FRN,2-Year
2026-05-27,NOTE,5-Year
2026-05-27,BILL,17-Week
2026-05-28,NOTE,7-Year
2026-05-28,BILL,4-Week
2026-05-28,BILL,8-Week
2026-06-01,BILL,13-Week
2026-06-01,BILL,26-Week
2026-06-02,BILL,6-Week
2026-06-03,BILL,17-Week
2026-06-04,BILL,4-Week
2026-06-04,BILL,8-Week
2026-06-08,BILL,13-Week
2026-06-08,BILL,26-Week
2026-06-09,BILL,6-Week
2026-06-09,BILL,52-Week
2026-06-09,NOTE,3-Year
2026-06-10,NOTE,10-Year
2026-06-10,BILL,17-Week
2026-06-11,BOND,30-Year
2026-06-11,BILL,4-Week
2026-06-11,BILL,8-Week
2026-06-15,BILL,13-Week
2026-06-15,BILL,26-Week
2026-06-16,BILL,6-Week
2026-06-16,BOND,20-Year
2026-06-17,BILL,17-Week
2026-06-18,BILL,4-Week
2026-06-18,BILL,8-Week
2026-06-18,TIPS,5-Year
2026-06-22,BILL,13-Week
2026-06-22,BILL,26-Week
2026-06-23,BILL,6-Week
2026-06-23,NOTE,2-Year
2026-06-24,FRN,2-Year
2026-06-24,NOTE,5-Year
2026-06-24,BILL,17-Week
2026-06-25,NOTE,7-Year
2026-06-25,BILL,4-Week
2026-06-25,BILL,8-Week
2026-06-29,BILL,13-Week
2026-06-29,BILL,26-Week
2026-06-30,BILL,6-Week
2026-07-01,BILL,17-Week
2026-07-02,BILL,4-Week
2026-07-02,BILL,8-Week
2026-07-06,BILL,13-Week
2026-07-06,BILL,26-Week
2026-07-07,BILL,6-Week
2026-07-07,BILL,52-Week
2026-07-07,NOTE,3-Year
2026-07-08,NOTE,10-Year
2026-07-08,BILL,17-Week
2026-07-09,BOND,30-Year
2026-07-09,BILL,4-Week
2026-07-09,BILL,8-Week
2026-07-13,BILL,13-Week
2026-07-13,BILL,26-Week
2026-07-14,BILL,6-Week
2026-07-15,BILL,17-Week
2026-07-16,BILL,4-Week
2026-07-16,BILL,8-Week
2026-07-20,BILL,13-Week
2026-07-20,BILL,26-Week
2026-07-21,BILL,6-Week
2026-07-22,BOND,20-Year
2026-07-22,BILL,17-Week
2026-07-23,BILL,4-Week
2026-07-23,BILL,8-Week
2026-07-23,TIPS,10-Year
2026-07-27,BILL,13-Week
2026-07-27,BILL,26-Week
2026-07-27,NOTE,2-Year
2026-07-27,NOTE,5-Year
2026-07-28,FRN,2-Year
2026-07-28,NOTE,7-Year
2026-07-29,BILL,17-Week
2026-07-30,BILL,4-Week
2026-07-30,BILL,8-Week
2026-08-03,BILL,13-Week
2026-08-03,BILL,26-Week
2026-08-04,BILL,6-Week
2026-08-04,BILL,52-Week
"""

# Build schedule dict: {date_str: [(term, sec_type), ...]}
AUCTION_SCHEDULE: dict[str, list[tuple[str, str]]] = defaultdict(list)
for _line in _RAW_SCHEDULE.strip().splitlines():
    _d, _t, _term = _line.strip().split(",")
    AUCTION_SCHEDULE[_d].append((_term, _t))

# ── Config ─────────────────────────────────────────────────────────────────

TREASURY_API  = "https://www.treasurydirect.gov/TA_WS/securities/search"
CURRENT_FILE  = Path("treasury_current.json")
PREVIOUS_FILE = Path("treasury_previous.json")

TYPE_EMOJI = {
    "BILL": "💵", "NOTE": "📄", "BOND": "🏛️",
    "TIPS": "📊", "FRN": "🔄",
}


# ── Schedule helpers ────────────────────────────────────────────────────────

def get_scheduled(auction_date: str) -> list[tuple[str, str]]:
    """Return [(term, type)] scheduled for this date."""
    return AUCTION_SCHEDULE.get(auction_date, [])


def upcoming_auctions(from_date: str, days: int = 4) -> list[tuple[str, list]]:
    """Return next N auction days after from_date."""
    start = date.fromisoformat(from_date)
    results = []
    for i in range(1, 30):
        d = (start + timedelta(days=i)).isoformat()
        if d in AUCTION_SCHEDULE:
            results.append((d, AUCTION_SCHEDULE[d]))
        if len(results) >= days:
            break
    return results


# ── Fetch ──────────────────────────────────────────────────────────────────

def fetch_auctions(auction_date: str) -> list[dict]:
    """Fetch all security types scheduled for this date from TreasuryDirect."""
    scheduled = get_scheduled(auction_date)
    if not scheduled:
        print(f"No auctions scheduled for {auction_date} per official schedule.")
        return []

    sec_types = list(dict.fromkeys(t for _, t in scheduled))  # unique, ordered
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
        except Exception as e:
            print(f"  Error fetching {sec_type}: {e}")

    return results


# ── Parse ──────────────────────────────────────────────────────────────────

def to_float(v) -> float:
    try:
        return float(v) if v not in (None, "", "null") else 0.0
    except (ValueError, TypeError):
        return 0.0


def pct(part: float, whole: float) -> float:
    return round(part / whole * 100, 1) if whole > 0 else 0.0


def parse_auction(raw: dict) -> dict:
    term     = raw.get("securityTerm", raw.get("term", "Unknown"))
    sec_type = raw.get("securityType", raw.get("type", ""))
    label    = f"{term} {sec_type}"

    offering       = to_float(raw.get("offeringAmount"))
    total_tendered = to_float(raw.get("totalTendered"))
    total_accepted = to_float(raw.get("totalAccepted"))
    direct_acc     = to_float(raw.get("directBidderAccepted"))
    indirect_acc   = to_float(raw.get("indirectBidderAccepted"))
    dealer_acc     = to_float(raw.get("primaryDealerAccepted"))
    high_rate      = to_float(raw.get("highDiscountRate") or raw.get("highYield"))
    btc            = to_float(raw.get("bidToCoverRatio"))

    return {
        "label":            label,
        "security_term":    term,
        "security_type":    sec_type,
        "auction_date":     raw.get("auctionDate", ""),
        "issue_date":       raw.get("issueDate", ""),
        "offering_m":       offering,
        "total_tendered_m": total_tendered,
        "total_accepted_m": total_accepted,
        "bid_to_cover":     btc,
        "high_rate_pct":    high_rate,
        "direct":   {"accepted_m": direct_acc,   "pct": pct(direct_acc,   total_accepted)},
        "indirect": {"accepted_m": indirect_acc,  "pct": pct(indirect_acc,  total_accepted)},
        "dealer":   {"accepted_m": dealer_acc,    "pct": pct(dealer_acc,    total_accepted)},
    }


# ── Persistence ────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {}


def data_hash(auctions: list) -> str:
    return hashlib.sha256(json.dumps(auctions, sort_keys=True).encode()).hexdigest()


def rotate_and_save(dataset: dict) -> bool:
    """Rotate current→previous, save new current. Returns True if changed."""
    current = load_json(CURRENT_FILE)
    changed = data_hash(dataset.get("auctions", [])) != data_hash(current.get("auctions", []))
    if changed and current:
        PREVIOUS_FILE.write_text(json.dumps(current, indent=2))
        print(f"Rotated → {PREVIOUS_FILE}")
    CURRENT_FILE.write_text(json.dumps(dataset, indent=2))
    print(f"Saved   → {CURRENT_FILE}")
    return changed


# ── Formatting ─────────────────────────────────────────────────────────────

def fmt_m(v: float) -> str:
    return f"${v/1000:.2f}B" if v >= 1000 else f"${v:.0f}M"


def btc_label(btc: float) -> str:
    if btc >= 2.5: return "🟢 Strong"
    if btc >= 2.0: return "🟡 Average"
    return "🔴 Weak"


# ── Discord ────────────────────────────────────────────────────────────────

def send_discord(auctions: list[dict], auction_date: str, upcoming: list) -> None:
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("No DISCORD_WEBHOOK_URL — skipping.")
        return

    fields = []

    # One field per auction
    for a in auctions:
        emoji = TYPE_EMOJI.get(a["security_type"], "📋")
        btc   = a["bid_to_cover"]
        value = (
            f"**Offered:** {fmt_m(a['offering_m'])}  "
            f"**Tendered:** {fmt_m(a['total_tendered_m'])}\n"
            f"**Bid-to-Cover:** `{btc:.2f}x`  {btc_label(btc)}\n"
            f"**High Rate:** `{a['high_rate_pct']:.3f}%`\n\n"
            f"**Buyer Breakdown** *(% of accepted)*\n"
            f"🏛️ Direct:           {fmt_m(a['direct']['accepted_m'])}  `{a['direct']['pct']}%`\n"
            f"🌍 Indirect/Foreign: {fmt_m(a['indirect']['accepted_m'])}  `{a['indirect']['pct']}%`\n"
            f"🏦 Primary Dealer:   {fmt_m(a['dealer']['accepted_m'])}  `{a['dealer']['pct']}%`"
        )
        fields.append({"name": f"{emoji} {a['label']}", "value": value, "inline": False})

    # Upcoming auctions field
    if upcoming:
        lines = []
        for d, items in upcoming[:3]:
            day = datetime.strptime(d, "%Y-%m-%d").strftime("%a %b %d")
            securities = ", ".join(f"{term} {t}" for term, t in items)
            lines.append(f"**{day}:** {securities}")
        fields.append({
            "name": "📅 Upcoming Auctions",
            "value": "\n".join(lines),
            "inline": False,
        })

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
    """Send upcoming schedule only — no results."""
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return

    fields = []
    for d, items in upcoming:
        day = datetime.strptime(d, "%Y-%m-%d").strftime("%A, %B %d")
        lines = []
        for term, sec_type in items:
            emoji = TYPE_EMOJI.get(sec_type, "📋")
            lines.append(f"{emoji} {term} {sec_type}")
        fields.append({"name": day, "value": "\n".join(lines), "inline": True})

    embed = {
        "title": f"📅 Upcoming Treasury Auctions — Week of {today}",
        "color": 0x1E90FF,
        "fields": fields,
        "footer": {"text": f"Source: US Treasury Tentative Auction Schedule  •  {today}"},
    }
    resp = requests.post(webhook_url, json={"embeds": [embed]}, timeout=10)
    resp.raise_for_status()
    print("Discord preview sent.")


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date",    default=date.today().isoformat())
    parser.add_argument("--force",   action="store_true")
    parser.add_argument("--preview", action="store_true",
                        help="Send upcoming schedule to Discord without fetching results")
    args = parser.parse_args()

    upcoming = upcoming_auctions(args.date, days=4)

    if args.preview:
        send_discord_preview(upcoming, args.date)
        return

    scheduled = get_scheduled(args.date)
    if not scheduled:
        print(f"No auctions scheduled for {args.date}.")
        sys.exit(0)

    scheduled_str = ", ".join(f"{t} {s}" for t, s in scheduled)
    print(f"Scheduled for {args.date}: {scheduled_str}")

    raw = fetch_auctions(args.date)
    if not raw:
        print("Results not yet posted (auction may still be open — retry after 1PM ET).")
        sys.exit(0)

    parsed  = [parse_auction(r) for r in raw]
    dataset = {
        "fetched_at":   datetime.now(timezone.utc).isoformat(),
        "auction_date": args.date,
        "scheduled":    scheduled,
        "auctions":     parsed,
    }

    # Print log summary
    for a in parsed:
        print(f"\n  {a['label']}")
        print(f"    Offered {fmt_m(a['offering_m'])} | Tendered {fmt_m(a['total_tendered_m'])} | BTC {a['bid_to_cover']:.2f}x | Rate {a['high_rate_pct']:.3f}%")
        print(f"    Direct {a['direct']['pct']}%  Indirect {a['indirect']['pct']}%  Dealer {a['dealer']['pct']}%")

    changed = rotate_and_save(dataset)

    if changed or args.force:
        print("\nData changed — alerting Discord.")
        send_discord(parsed, args.date, upcoming)
    else:
        print("\nUnchanged — no alert sent.")


if __name__ == "__main__":
    main()
