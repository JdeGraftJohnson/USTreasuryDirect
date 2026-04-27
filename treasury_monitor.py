"""
treasury_monitor.py — US Treasury auction monitor for GitHub Actions.

Fetches today's Bill/Note/Bond auction results from TreasuryDirect,
displays bid breakdown (direct, indirect, foreign/primary dealer),
retains last 2 datasets, and only alerts Discord if data changed.

Run:
    python treasury_monitor.py          # fetch today
    python treasury_monitor.py --date 2026-04-25   # specific date
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import requests

# ── Config ─────────────────────────────────────────────────────────────────

TREASURY_API = "https://www.treasurydirect.gov/TA_WS/securities/search"
CURRENT_FILE = Path("treasury_current.json")
PREVIOUS_FILE = Path("treasury_previous.json")

# Security types to monitor (add "Note", "Bond", "TIPS" as needed)
MONITOR_TYPES = ["Bill"]


# ── Fetch ──────────────────────────────────────────────────────────────────

def fetch_auctions(auction_date: str) -> list[dict]:
    """
    Fetch auction results from TreasuryDirect for a given date.
    Returns list of auction records.
    """
    results = []
    for sec_type in MONITOR_TYPES:
        try:
            resp = requests.get(
                TREASURY_API,
                params={
                    "startDate": auction_date,
                    "endDate": auction_date,
                    "type": sec_type,
                },
                headers={"User-Agent": "TreasuryMonitor/1.0"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                results.extend(data)
            print(f"Fetched {len(data)} {sec_type} auction(s) for {auction_date}")
        except requests.HTTPError as e:
            print(f"HTTP error fetching {sec_type}: {e}")
        except Exception as e:
            print(f"Error fetching {sec_type}: {e}")
    return results


# ── Parse ──────────────────────────────────────────────────────────────────

def parse_auction(raw: dict) -> dict:
    """
    Extract and normalise the fields we care about from a raw API record.

    TreasuryDirect field reference:
      securityTerm          e.g. "4-Week", "13-Week", "26-Week", "52-Week"
      securityType          Bill / Note / Bond / TIPS
      auctionDate           YYYY-MM-DD
      issueDate             YYYY-MM-DD
      offeringAmount        Total offered ($M)
      totalTendered         Total bids submitted ($M)
      totalAccepted         Total bids accepted ($M)
      directBidderTendered  Direct buyer bids submitted ($M)
      directBidderAccepted  Direct buyer bids accepted ($M)
      indirectBidderTendered
      indirectBidderAccepted
      primaryDealerTendered
      primaryDealerAccepted
      highDiscountRate      High yield / stop-out rate (%)
      bidToCoverRatio       Total tendered / total accepted
    """
    def to_float(v) -> float:
        try:
            return float(v) if v not in (None, "", "null") else 0.0
        except (ValueError, TypeError):
            return 0.0

    term = raw.get("securityTerm", raw.get("term", "Unknown"))
    sec_type = raw.get("securityType", raw.get("type", "Bill"))
    label = f"{term} {sec_type}"

    offering        = to_float(raw.get("offeringAmount"))
    total_tendered  = to_float(raw.get("totalTendered"))
    total_accepted  = to_float(raw.get("totalAccepted"))

    direct_tend     = to_float(raw.get("directBidderTendered"))
    direct_acc      = to_float(raw.get("directBidderAccepted"))
    indirect_tend   = to_float(raw.get("indirectBidderTendered"))
    indirect_acc    = to_float(raw.get("indirectBidderAccepted"))
    dealer_tend     = to_float(raw.get("primaryDealerTendered"))
    dealer_acc      = to_float(raw.get("primaryDealerAccepted"))

    high_rate       = to_float(raw.get("highDiscountRate", raw.get("highYield")))
    btc             = to_float(raw.get("bidToCoverRatio"))

    # % of accepted going to each buyer type
    def pct(part, whole):
        return round((part / whole * 100), 1) if whole > 0 else 0.0

    return {
        "label":             label,
        "security_term":     term,
        "security_type":     sec_type,
        "auction_date":      raw.get("auctionDate", ""),
        "issue_date":        raw.get("issueDate", ""),
        "offering_amount_m": offering,
        "total_tendered_m":  total_tendered,
        "total_accepted_m":  total_accepted,
        "bid_to_cover":      btc,
        "high_rate_pct":     high_rate,
        "direct": {
            "tendered_m":  direct_tend,
            "accepted_m":  direct_acc,
            "pct_of_accepted": pct(direct_acc, total_accepted),
        },
        "indirect": {
            "tendered_m":  indirect_tend,
            "accepted_m":  indirect_acc,
            "pct_of_accepted": pct(indirect_acc, total_accepted),
        },
        "primary_dealer": {
            "tendered_m":  dealer_tend,
            "accepted_m":  dealer_acc,
            "pct_of_accepted": pct(dealer_acc, total_accepted),
        },
    }


# ── Persistence ────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {}


def data_hash(auctions: list[dict]) -> str:
    """Stable hash of the auction data to detect changes."""
    serialised = json.dumps(auctions, sort_keys=True)
    return hashlib.sha256(serialised.encode()).hexdigest()


def rotate_files(new_data: dict) -> bool:
    """
    Rotate current → previous, write new current.
    Returns True if data changed vs previous current.
    """
    current = load_json(CURRENT_FILE)
    changed = data_hash(new_data.get("auctions", [])) != data_hash(current.get("auctions", []))

    if changed and current:
        PREVIOUS_FILE.write_text(json.dumps(current, indent=2))
        print(f"Rotated current → {PREVIOUS_FILE}")

    CURRENT_FILE.write_text(json.dumps(new_data, indent=2))
    print(f"Saved current → {CURRENT_FILE}")
    return changed


# ── Formatting ─────────────────────────────────────────────────────────────

def fmt_m(value_m: float) -> str:
    """Format million-dollar value as $XB or $XM."""
    if value_m >= 1000:
        return f"${value_m/1000:.2f}B"
    return f"${value_m:.0f}M"


def format_summary(auction: dict) -> str:
    """Plain-text summary of one auction."""
    lines = [
        f"{'─'*44}",
        f"  {auction['label']}  |  {auction['auction_date']}",
        f"{'─'*44}",
        f"  Offered:        {fmt_m(auction['offering_amount_m'])}",
        f"  Total Tendered: {fmt_m(auction['total_tendered_m'])}",
        f"  Bid-to-Cover:   {auction['bid_to_cover']:.2f}x",
        f"  High Rate:      {auction['high_rate_pct']:.3f}%",
        f"",
        f"  Buyer Breakdown (% of accepted):",
        f"    Direct:         {fmt_m(auction['direct']['accepted_m'])}  ({auction['direct']['pct_of_accepted']}%)",
        f"    Indirect:       {fmt_m(auction['indirect']['accepted_m'])}  ({auction['indirect']['pct_of_accepted']}%)",
        f"    Primary Dealer: {fmt_m(auction['primary_dealer']['accepted_m'])}  ({auction['primary_dealer']['pct_of_accepted']}%)",
    ]
    return "\n".join(lines)


# ── Discord ────────────────────────────────────────────────────────────────

def btc_signal(btc: float) -> str:
    if btc >= 2.5:
        return "🟢 Strong demand"
    if btc >= 2.0:
        return "🟡 Average demand"
    return "🔴 Weak demand"


def send_discord(auctions: list[dict], auction_date: str) -> None:
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("No DISCORD_WEBHOOK_URL — skipping Discord alert.")
        return

    fields = []
    for a in auctions:
        btc = a["bid_to_cover"]
        signal = btc_signal(btc)

        value = (
            f"**Offered:** {fmt_m(a['offering_amount_m'])}  "
            f"**Tendered:** {fmt_m(a['total_tendered_m'])}\n"
            f"**Bid-to-Cover:** `{btc:.2f}x`  {signal}\n"
            f"**High Rate:** `{a['high_rate_pct']:.3f}%`\n\n"
            f"**Buyer Breakdown**\n"
            f"🏛️ Direct:         {fmt_m(a['direct']['accepted_m'])} `({a['direct']['pct_of_accepted']}%)`\n"
            f"🌍 Indirect/Foreign: {fmt_m(a['indirect']['accepted_m'])} `({a['indirect']['pct_of_accepted']}%)`\n"
            f"🏦 Primary Dealer: {fmt_m(a['primary_dealer']['accepted_m'])} `({a['primary_dealer']['pct_of_accepted']}%)`"
        )

        fields.append({
            "name": f"📋 {a['label']}",
            "value": value,
            "inline": False,
        })

    embed = {
        "title": f"🏛️ US Treasury Auction Results — {auction_date}",
        "color": 0x1E90FF,
        "fields": fields,
        "footer": {
            "text": f"TreasuryDirect • {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        },
    }

    resp = requests.post(webhook_url, json={"embeds": [embed]}, timeout=10)
    resp.raise_for_status()
    print(f"Discord alert sent — {len(auctions)} auction(s).")


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="US Treasury auction monitor")
    parser.add_argument("--date", default=date.today().isoformat(),
                        help="Auction date YYYY-MM-DD (default: today)")
    parser.add_argument("--force", action="store_true",
                        help="Send Discord alert even if data unchanged")
    args = parser.parse_args()

    print(f"Fetching Treasury auctions for {args.date}...")
    raw_auctions = fetch_auctions(args.date)

    if not raw_auctions:
        print("No auction data found for this date (market may be closed or results not yet posted).")
        sys.exit(0)

    parsed = [parse_auction(r) for r in raw_auctions]

    # Print summary to logs
    for a in parsed:
        print(format_summary(a))

    # Build dataset with timestamp
    dataset = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "auction_date": args.date,
        "auctions": parsed,
    }

    changed = rotate_files(dataset)

    if changed or args.force:
        print("Data changed — sending Discord alert.")
        send_discord(parsed, args.date)
    else:
        print("Data unchanged since last run — no alert sent.")


if __name__ == "__main__":
    main()
