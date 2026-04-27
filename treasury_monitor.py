"""
treasury_monitor.py — US Treasury auction monitor using FiscalData API.

Switched from TreasuryDirect TA_WS (blocks GitHub IPs) to:
  https://api.fiscaldata.treasury.gov/services/api/fiscal_service/

No API key required. Full docs:
  https://fiscaldata.treasury.gov/api-documentation/

Run:
    python treasury_monitor.py              # auto date
    python treasury_monitor.py --preview    # send upcoming schedule to Discord
    python treasury_monitor.py --force      # alert even if unchanged
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

from auction_schedule import (
    get_scheduled,
    most_recent_auction_date,
    upcoming_auctions,
)

# ── FiscalData API ─────────────────────────────────────────────────────────
# Endpoint: /v1/accounting/od/auctions_query
# Docs: https://fiscaldata.treasury.gov/datasets/treasury-securities-auctions-data/
#
# Key fields returned:
#   auction_date, security_type, security_term, offering_amt,
#   total_tendered, total_accepted, bid_to_cover_ratio,
#   direct_bidder_accepted, indirect_bidder_accepted, primary_dealer_accepted,
#   high_rate, high_yield, issue_date

FISCALDATA_BASE = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
AUCTION_ENDPOINT = f"{FISCALDATA_BASE}/v1/accounting/od/auctions_query"

CURRENT_FILE  = Path("treasury_current.json")
PREVIOUS_FILE = Path("treasury_previous.json")

TYPE_EMOJI = {"Bill": "💵", "Note": "📄", "Bond": "🏛️", "TIPS": "📊", "FRN": "🔄"}


# ── Fetch ──────────────────────────────────────────────────────────────────

def fetch_auctions(auction_date: str) -> list[dict]:
    """
    Fetch auction results from FiscalData for a given date.
    FiscalData field names use snake_case and title-case type values.
    """
    scheduled = get_scheduled(auction_date)
    if not scheduled:
        return []

    # Get unique security types scheduled (title-case to match FiscalData)
    type_map = {"BILL": "Bill", "NOTE": "Note", "BOND": "Bond", "TIPS": "TIPS", "FRN": "FRN"}
    sec_types = list(dict.fromkeys(type_map.get(t, t) for _, t in scheduled))

    results = []
    for sec_type in sec_types:
        try:
            resp = requests.get(
                AUCTION_ENDPOINT,
                params={
                    "filter": f"auction_date:eq:{auction_date},security_type:eq:{sec_type}",
                    "sort":   "-auction_date",
                    "page[size]": "50",
                    "format": "json",
                },
                headers={"User-Agent": "TreasuryMonitor/1.0"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            records = data.get("data", [])
            results.extend(records)
            print(f"  Fetched {len(records)} {sec_type}(s) from FiscalData")
        except requests.HTTPError as e:
            print(f"  HTTP error {sec_type}: {e}")
        except Exception as e:
            print(f"  Error {sec_type}: {e}")

    return results


# ── Parse ──────────────────────────────────────────────────────────────────

def _f(v) -> float:
    """Safely convert FiscalData string value to float."""
    try:
        return float(v) if v not in (None, "", "null", "NULL") else 0.0
    except (ValueError, TypeError):
        return 0.0


def _pct(part: float, whole: float) -> float:
    return round(part / whole * 100, 1) if whole > 0 else 0.0


def parse_auction(raw: dict) -> dict:
    """
    Parse a FiscalData auction record.
    FiscalData field reference:
      security_type, security_term, auction_date, issue_date
      offering_amt, total_tendered, total_accepted
      bid_to_cover_ratio, high_rate, high_yield
      direct_bidder_accepted, indirect_bidder_accepted, primary_dealer_accepted
    """
    term     = raw.get("security_term", "Unknown")
    sec_type = raw.get("security_type", "")

    offering       = _f(raw.get("offering_amt"))
    total_tendered = _f(raw.get("total_tendered"))
    total_accepted = _f(raw.get("total_accepted"))
    direct_acc     = _f(raw.get("direct_bidder_accepted"))
    indirect_acc   = _f(raw.get("indirect_bidder_accepted"))
    dealer_acc     = _f(raw.get("primary_dealer_accepted"))
    # Bills use high_rate (discount rate), Notes/Bonds use high_yield
    high_rate      = _f(raw.get("high_rate") or raw.get("high_yield"))
    btc            = _f(raw.get("bid_to_cover_ratio"))

    return {
        "label":            f"{term} {sec_type}",
        "security_term":    term,
        "security_type":    sec_type,
        "auction_date":     raw.get("auction_date", ""),
        "issue_date":       raw.get("issue_date", ""),
        "maturity_date":    raw.get("maturity_date", ""),
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
    """Format raw dollar amounts as human-readable strings.
    FiscalData returns actual dollar values (e.g. 89000000000 = $89 billion).
    """
    if v == 0:
        return "$0"
    if v >= 1_000_000_000_000:
        return f"${v/1_000_000_000_000:.1f} trillion"
    if v >= 1_000_000_000:
        n = v / 1_000_000_000
        return f"${n:.0f} billion" if n == int(n) else f"${n:.1f} billion"
    if v >= 1_000_000:
        n = v / 1_000_000
        return f"${n:.0f} million" if n == int(n) else f"${n:.1f} million"
    return f"${v:,.0f}"

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
        # Format dates nicely: 2026-04-27 → Apr 27, 2026
        def _fmtdate(d):
            try: return datetime.strptime(d, "%Y-%m-%d").strftime("%b %d, %Y")
            except: return d or "—"
        auction_dt  = _fmtdate(a["auction_date"])
        maturity_dt = _fmtdate(a["maturity_date"])
        value = (
            f"📅 **Auction:** {auction_dt}  |  **Matures:** {maturity_dt}\n"
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
        "footer": {
            "text": f"FiscalData.treasury.gov  •  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        },
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

    today    = datetime.now(timezone.utc).date().isoformat()
    upcoming = upcoming_auctions(from_date=today, days=4)

    if args.preview:
        send_discord_preview(upcoming, today)
        return

    auction_date = most_recent_auction_date()
    if not auction_date:
        print("No scheduled auction dates found in the past 7 days.")
        sys.exit(0)

    scheduled = get_scheduled(auction_date)
    print(f"Auto-selected: {auction_date}")
    print(f"Scheduled:     {', '.join(f'{t} {s}' for t,s in scheduled)}")
    print(f"API:           FiscalData (api.fiscaldata.treasury.gov)")

    raw     = fetch_auctions(auction_date)
    if not raw:
        print("No results yet — FiscalData posts results after auction settles (~1PM ET).")
        sys.exit(0)

    parsed  = [parse_auction(r) for r in raw]

    for a in parsed:
        print(
            f"  {a['label']}: BTC {a['bid_to_cover']:.2f}x | "
            f"Rate {a['high_rate_pct']:.3f}% | "
            f"Direct {a['direct']['pct']}% "
            f"Indirect {a['indirect']['pct']}% "
            f"Dealer {a['dealer']['pct']}%"
        )

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
