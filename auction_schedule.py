"""
auction_schedule.py — Official US Treasury Tentative Auction Schedule.

Source: https://www.treasurydirect.gov/auctions/announcements-data-results/
        announcement-results-press-releases/

Update this file each time Treasury publishes a new tentative schedule
(typically every 6 months). Replace the AUCTION_SCHEDULE dict below.

Format: {"YYYY-MM-DD": [("Term", "Type"), ...]}

Types: BILL, NOTE, BOND, TIPS, FRN
Terms: 4-Week, 6-Week, 8-Week, 13-Week, 17-Week, 26-Week, 52-Week,
       2-Year, 3-Year, 5-Year, 7-Year, 10-Year, 20-Year, 30-Year
"""

from collections import defaultdict
from datetime import date, timedelta

# ── Schedule (Feb 2026 – Aug 2026) ────────────────────────────────────────

_RAW = [
    # Feb 2026
    ("2026-02-09", "BILL", "13-Week"),
    ("2026-02-09", "BILL", "26-Week"),
    ("2026-02-10", "BILL", "6-Week"),
    ("2026-02-10", "NOTE", "3-Year"),
    ("2026-02-11", "NOTE", "10-Year"),
    ("2026-02-11", "BILL", "17-Week"),
    ("2026-02-12", "BOND", "30-Year"),
    ("2026-02-12", "BILL", "4-Week"),
    ("2026-02-12", "BILL", "8-Week"),
    ("2026-02-17", "BILL", "6-Week"),
    ("2026-02-17", "BILL", "13-Week"),
    ("2026-02-17", "BILL", "26-Week"),
    ("2026-02-17", "BILL", "52-Week"),
    ("2026-02-18", "BOND", "20-Year"),
    ("2026-02-18", "BILL", "17-Week"),
    ("2026-02-19", "BILL", "4-Week"),
    ("2026-02-19", "BILL", "8-Week"),
    ("2026-02-19", "TIPS", "30-Year"),
    ("2026-02-23", "BILL", "13-Week"),
    ("2026-02-23", "BILL", "26-Week"),
    ("2026-02-24", "BILL", "6-Week"),
    ("2026-02-24", "NOTE", "2-Year"),
    ("2026-02-25", "FRN",  "2-Year"),
    ("2026-02-25", "NOTE", "5-Year"),
    ("2026-02-25", "BILL", "17-Week"),
    ("2026-02-26", "NOTE", "7-Year"),
    ("2026-02-26", "BILL", "4-Week"),
    ("2026-02-26", "BILL", "8-Week"),
    # Mar 2026
    ("2026-03-02", "BILL", "13-Week"),
    ("2026-03-02", "BILL", "26-Week"),
    ("2026-03-03", "BILL", "6-Week"),
    ("2026-03-04", "BILL", "17-Week"),
    ("2026-03-05", "BILL", "4-Week"),
    ("2026-03-05", "BILL", "8-Week"),
    ("2026-03-09", "BILL", "13-Week"),
    ("2026-03-09", "BILL", "26-Week"),
    ("2026-03-10", "BILL", "6-Week"),
    ("2026-03-10", "NOTE", "3-Year"),
    ("2026-03-11", "NOTE", "10-Year"),
    ("2026-03-11", "BILL", "17-Week"),
    ("2026-03-12", "BOND", "30-Year"),
    ("2026-03-12", "BILL", "4-Week"),
    ("2026-03-12", "BILL", "8-Week"),
    ("2026-03-16", "BILL", "13-Week"),
    ("2026-03-16", "BILL", "26-Week"),
    ("2026-03-17", "BILL", "6-Week"),
    ("2026-03-17", "BILL", "52-Week"),
    ("2026-03-17", "BOND", "20-Year"),
    ("2026-03-18", "BILL", "17-Week"),
    ("2026-03-19", "BILL", "4-Week"),
    ("2026-03-19", "BILL", "8-Week"),
    ("2026-03-19", "TIPS", "10-Year"),
    ("2026-03-23", "BILL", "13-Week"),
    ("2026-03-23", "BILL", "26-Week"),
    ("2026-03-24", "BILL", "6-Week"),
    ("2026-03-24", "NOTE", "2-Year"),
    ("2026-03-25", "FRN",  "2-Year"),
    ("2026-03-25", "NOTE", "5-Year"),
    ("2026-03-25", "BILL", "17-Week"),
    ("2026-03-26", "NOTE", "7-Year"),
    ("2026-03-26", "BILL", "4-Week"),
    ("2026-03-26", "BILL", "8-Week"),
    ("2026-03-30", "BILL", "13-Week"),
    ("2026-03-30", "BILL", "26-Week"),
    ("2026-03-31", "BILL", "6-Week"),
    # Apr 2026
    ("2026-04-01", "BILL", "17-Week"),
    ("2026-04-02", "BILL", "4-Week"),
    ("2026-04-02", "BILL", "8-Week"),
    ("2026-04-06", "BILL", "13-Week"),
    ("2026-04-06", "BILL", "26-Week"),
    ("2026-04-07", "BILL", "6-Week"),
    ("2026-04-07", "NOTE", "3-Year"),
    ("2026-04-08", "NOTE", "10-Year"),
    ("2026-04-08", "BILL", "17-Week"),
    ("2026-04-09", "BOND", "30-Year"),
    ("2026-04-09", "BILL", "4-Week"),
    ("2026-04-09", "BILL", "8-Week"),
    ("2026-04-13", "BILL", "13-Week"),
    ("2026-04-13", "BILL", "26-Week"),
    ("2026-04-14", "BILL", "6-Week"),
    ("2026-04-14", "BILL", "52-Week"),
    ("2026-04-15", "BILL", "17-Week"),
    ("2026-04-16", "BILL", "4-Week"),
    ("2026-04-16", "BILL", "8-Week"),
    ("2026-04-20", "BILL", "13-Week"),
    ("2026-04-20", "BILL", "26-Week"),
    ("2026-04-21", "BILL", "6-Week"),
    ("2026-04-22", "BOND", "20-Year"),
    ("2026-04-22", "BILL", "17-Week"),
    ("2026-04-23", "BILL", "4-Week"),
    ("2026-04-23", "BILL", "8-Week"),
    ("2026-04-23", "TIPS", "5-Year"),
    ("2026-04-27", "BILL", "13-Week"),
    ("2026-04-27", "BILL", "26-Week"),
    ("2026-04-27", "NOTE", "2-Year"),
    ("2026-04-27", "NOTE", "5-Year"),
    ("2026-04-28", "BILL", "6-Week"),
    ("2026-04-28", "FRN",  "2-Year"),
    ("2026-04-28", "NOTE", "7-Year"),
    ("2026-04-29", "BILL", "17-Week"),
    ("2026-04-30", "BILL", "4-Week"),
    ("2026-04-30", "BILL", "8-Week"),
    # May 2026
    ("2026-05-04", "BILL", "13-Week"),
    ("2026-05-04", "BILL", "26-Week"),
    ("2026-05-05", "BILL", "6-Week"),
    ("2026-05-06", "BILL", "17-Week"),
    ("2026-05-07", "BILL", "4-Week"),
    ("2026-05-07", "BILL", "8-Week"),
    ("2026-05-11", "BILL", "13-Week"),
    ("2026-05-11", "BILL", "26-Week"),
    ("2026-05-11", "NOTE", "3-Year"),
    ("2026-05-12", "NOTE", "10-Year"),
    ("2026-05-12", "BILL", "6-Week"),
    ("2026-05-12", "BILL", "52-Week"),
    ("2026-05-13", "BOND", "30-Year"),
    ("2026-05-13", "BILL", "17-Week"),
    ("2026-05-14", "BILL", "4-Week"),
    ("2026-05-14", "BILL", "8-Week"),
    ("2026-05-18", "BILL", "13-Week"),
    ("2026-05-18", "BILL", "26-Week"),
    ("2026-05-19", "BILL", "6-Week"),
    ("2026-05-20", "BOND", "20-Year"),
    ("2026-05-20", "BILL", "17-Week"),
    ("2026-05-21", "BILL", "4-Week"),
    ("2026-05-21", "BILL", "8-Week"),
    ("2026-05-21", "TIPS", "10-Year"),
    ("2026-05-26", "BILL", "6-Week"),
    ("2026-05-26", "BILL", "13-Week"),
    ("2026-05-26", "BILL", "26-Week"),
    ("2026-05-26", "NOTE", "2-Year"),
    ("2026-05-27", "FRN",  "2-Year"),
    ("2026-05-27", "NOTE", "5-Year"),
    ("2026-05-27", "BILL", "17-Week"),
    ("2026-05-28", "NOTE", "7-Year"),
    ("2026-05-28", "BILL", "4-Week"),
    ("2026-05-28", "BILL", "8-Week"),
    # Jun 2026
    ("2026-06-01", "BILL", "13-Week"),
    ("2026-06-01", "BILL", "26-Week"),
    ("2026-06-02", "BILL", "6-Week"),
    ("2026-06-03", "BILL", "17-Week"),
    ("2026-06-04", "BILL", "4-Week"),
    ("2026-06-04", "BILL", "8-Week"),
    ("2026-06-08", "BILL", "13-Week"),
    ("2026-06-08", "BILL", "26-Week"),
    ("2026-06-09", "BILL", "6-Week"),
    ("2026-06-09", "BILL", "52-Week"),
    ("2026-06-09", "NOTE", "3-Year"),
    ("2026-06-10", "NOTE", "10-Year"),
    ("2026-06-10", "BILL", "17-Week"),
    ("2026-06-11", "BOND", "30-Year"),
    ("2026-06-11", "BILL", "4-Week"),
    ("2026-06-11", "BILL", "8-Week"),
    ("2026-06-15", "BILL", "13-Week"),
    ("2026-06-15", "BILL", "26-Week"),
    ("2026-06-16", "BILL", "6-Week"),
    ("2026-06-16", "BOND", "20-Year"),
    ("2026-06-17", "BILL", "17-Week"),
    ("2026-06-18", "BILL", "4-Week"),
    ("2026-06-18", "BILL", "8-Week"),
    ("2026-06-18", "TIPS", "5-Year"),
    ("2026-06-22", "BILL", "13-Week"),
    ("2026-06-22", "BILL", "26-Week"),
    ("2026-06-23", "BILL", "6-Week"),
    ("2026-06-23", "NOTE", "2-Year"),
    ("2026-06-24", "FRN",  "2-Year"),
    ("2026-06-24", "NOTE", "5-Year"),
    ("2026-06-24", "BILL", "17-Week"),
    ("2026-06-25", "NOTE", "7-Year"),
    ("2026-06-25", "BILL", "4-Week"),
    ("2026-06-25", "BILL", "8-Week"),
    ("2026-06-29", "BILL", "13-Week"),
    ("2026-06-29", "BILL", "26-Week"),
    ("2026-06-30", "BILL", "6-Week"),
    # Jul 2026
    ("2026-07-01", "BILL", "17-Week"),
    ("2026-07-02", "BILL", "4-Week"),
    ("2026-07-02", "BILL", "8-Week"),
    ("2026-07-06", "BILL", "13-Week"),
    ("2026-07-06", "BILL", "26-Week"),
    ("2026-07-07", "BILL", "6-Week"),
    ("2026-07-07", "BILL", "52-Week"),
    ("2026-07-07", "NOTE", "3-Year"),
    ("2026-07-08", "NOTE", "10-Year"),
    ("2026-07-08", "BILL", "17-Week"),
    ("2026-07-09", "BOND", "30-Year"),
    ("2026-07-09", "BILL", "4-Week"),
    ("2026-07-09", "BILL", "8-Week"),
    ("2026-07-13", "BILL", "13-Week"),
    ("2026-07-13", "BILL", "26-Week"),
    ("2026-07-14", "BILL", "6-Week"),
    ("2026-07-15", "BILL", "17-Week"),
    ("2026-07-16", "BILL", "4-Week"),
    ("2026-07-16", "BILL", "8-Week"),
    ("2026-07-20", "BILL", "13-Week"),
    ("2026-07-20", "BILL", "26-Week"),
    ("2026-07-21", "BILL", "6-Week"),
    ("2026-07-22", "BOND", "20-Year"),
    ("2026-07-22", "BILL", "17-Week"),
    ("2026-07-23", "BILL", "4-Week"),
    ("2026-07-23", "BILL", "8-Week"),
    ("2026-07-23", "TIPS", "10-Year"),
    ("2026-07-27", "BILL", "13-Week"),
    ("2026-07-27", "BILL", "26-Week"),
    ("2026-07-27", "NOTE", "2-Year"),
    ("2026-07-27", "NOTE", "5-Year"),
    ("2026-07-28", "FRN",  "2-Year"),
    ("2026-07-28", "NOTE", "7-Year"),
    ("2026-07-29", "BILL", "17-Week"),
    ("2026-07-30", "BILL", "4-Week"),
    ("2026-07-30", "BILL", "8-Week"),
    # Aug 2026
    ("2026-08-03", "BILL", "13-Week"),
    ("2026-08-03", "BILL", "26-Week"),
    ("2026-08-04", "BILL", "6-Week"),
    ("2026-08-04", "BILL", "52-Week"),
]

# Build lookup dict
AUCTION_SCHEDULE: dict[str, list[tuple[str, str]]] = defaultdict(list)
for _date, _type, _term in _RAW:
    AUCTION_SCHEDULE[_date].append((_term, _type))

# Sorted list of all auction dates
ALL_DATES: list[str] = sorted(AUCTION_SCHEDULE.keys())


def get_scheduled(auction_date: str) -> list[tuple[str, str]]:
    """Return [(term, type)] scheduled for this date. Empty if none."""
    return list(AUCTION_SCHEDULE.get(auction_date, []))


def most_recent_auction_date(from_date: str | None = None) -> str | None:
    """
    Return the most recent auction date on or before from_date.
    Looks back up to 7 days to find the last scheduled date.
    Returns None if no scheduled date found in range.
    """
    pivot = date.fromisoformat(from_date) if from_date else date.today()
    for i in range(7):
        candidate = (pivot - timedelta(days=i)).isoformat()
        if candidate in AUCTION_SCHEDULE:
            return candidate
    return None


def upcoming_auctions(from_date: str | None = None, days: int = 4) -> list[tuple[str, list]]:
    """
    Return the next N auction days strictly after from_date.
    """
    pivot = date.fromisoformat(from_date) if from_date else date.today()
    results = []
    for d in ALL_DATES:
        if date.fromisoformat(d) > pivot:
            results.append((d, AUCTION_SCHEDULE[d]))
        if len(results) >= days:
            break
    return results


if __name__ == "__main__":
    # Quick self-test
    today = date.today().isoformat()
    recent = most_recent_auction_date()
    print(f"Today:              {today}")
    print(f"Most recent auction: {recent}")
    if recent:
        items = get_scheduled(recent)
        print(f"Scheduled:          {', '.join(f'{t} {s}' for t,s in items)}")
    print(f"\nUpcoming ({today}):")
    for d, items in upcoming_auctions(days=5):
        print(f"  {d}: {', '.join(f'{t} {s}' for t,s in items)}")
