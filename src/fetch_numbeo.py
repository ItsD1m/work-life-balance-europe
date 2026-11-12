"""Κατεβάζει από το Numbeo τους μέσους καθαρούς μισθούς και τα ενοίκια ανά πόλη.

Το Numbeo δημοσιεύει πίνακες "τιμές ανά πόλη" για κάθε γεωγραφική περιοχή.
Μας ενδιαφέρουν δύο είδη:
    itemId=105 -> Average Monthly Net Salary (After Tax)   [πάντα]
    itemId=26  -> Apartment (1 bedroom) in City Centre      [μόνο με --with-rent]

Έξοδος: data/numbeo_prices.csv
"""

from __future__ import annotations

import argparse
import csv
import html
import re
import sys
import time
from pathlib import Path

import requests

try:  # ο Avast κάνει MITM το HTTPS· το truststore διαβάζει το cert store των Windows
    import truststore

    truststore.inject_into_ssl()
except ImportError:  # pragma: no cover
    pass

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "numbeo_prices.csv"

BASE = "https://www.numbeo.com/cost-of-living/region_prices_by_city"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

REGION = 150  # Numbeo region id για την Ευρώπη
REGION_NAME = "Europe"

SALARY_ITEM = 105
RENT_ITEM = 26  # Apartment (1 bedroom) in City Centre

ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
TAG_RE = re.compile(r"<[^>]+>")


def _text(fragment: str) -> str:
    return html.unescape(TAG_RE.sub("", fragment)).strip()


def scrape(item_id: int, region_id: int, currency: str = "USD") -> dict[str, float]:
    """Επιστρέφει {"Πόλη, Χώρα": τιμή} για ένα item και μία περιοχή."""
    params = {"itemId": item_id, "region": region_id, "displayCurrency": currency}

    # Το Numbeo επιστρέφει 429 αν χτυπήσεις τις σελίδες στη σειρά· backoff και ξαναδοκίμασε.
    for attempt in range(6):
        response = requests.get(BASE, params=params, headers=HEADERS, timeout=60)
        if response.status_code != 429:
            break
        wait = 30 * (attempt + 1)
        print(f"    429 από το Numbeo, αναμονή {wait}s...", file=sys.stderr)
        time.sleep(wait)
    response.raise_for_status()

    prices: dict[str, float] = {}
    for row in ROW_RE.findall(response.text):
        cells = [_text(c) for c in CELL_RE.findall(row)]
        # Ο πίνακας είναι: [κενό rank], "Πόλη, Χώρα", "1234.56"
        if len(cells) != 3 or "," not in cells[1]:
            continue
        try:
            prices[cells[1]] = float(cells[2].replace(",", ""))
        except ValueError:
            continue
    return prices


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--currency", default="USD", help="νόμισμα εμφάνισης (default: USD)")
    parser.add_argument(
        "--with-rent", action="store_true",
        help="κατέβασε και το ενοίκιο γκαρσονιέρας στο κέντρο (δεύτερο αίτημα· "
             "το Numbeo κόβει πιο εύκολα την IP)",
    )
    args = parser.parse_args()
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    items = {SALARY_ITEM: "net_salary_usd"}
    if args.with_rent:
        items[RENT_ITEM] = "rent_1br_centre_usd"

    merged: dict[str, dict[str, float]] = {}
    for item_id, column in items.items():
        prices = scrape(item_id, REGION, args.currency)
        print(f"  {column:<22} {len(prices):>3} πόλεις", file=sys.stderr)
        for city, value in prices.items():
            merged.setdefault(city, {})[column] = value
        time.sleep(5)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["city_numbeo", "country", *items.values()])
        for city in sorted(merged):
            name, _, country = city.rpartition(", ")
            writer.writerow(
                [name, country, *(merged[city].get(col, "") for col in items.values())]
            )

    print(f"Γράφτηκαν {len(merged)} πόλεις στο {OUT.relative_to(ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
