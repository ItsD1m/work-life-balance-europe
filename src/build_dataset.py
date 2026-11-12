"""Ενώνει τον δείκτη ισορροπίας με τους μισθούς και κρατάει μόνο τις ευρωπαϊκές πόλεις.

Είσοδοι:
    data/wlb_index_2025_raw.csv  (Blueground, και οι 75 πόλεις - στατικό)
    data/numbeo_prices.csv       (Numbeo, από το fetch_numbeo.py)

Έξοδος:
    data/europe_work_life_balance.csv
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_CSV = ROOT / "data" / "wlb_index_2025_raw.csv"
PRICES_CSV = ROOT / "data" / "numbeo_prices.csv"
OUT_CSV = ROOT / "data" / "europe_work_life_balance.csv"

# Οι ευρωπαϊκές χώρες που εμφανίζονται στον δείκτη των 75 πόλεων.
EUROPEAN_COUNTRIES = {
    "Austria", "Belgium", "Denmark", "Finland", "France", "Germany", "Greece",
    "Hungary", "Ireland", "Italy", "Luxembourg", "Netherlands", "Norway",
    "Portugal", "Spain", "Sweden", "Switzerland", "United Kingdom",
}

# Η Κωνσταντινούπολη (#74) είναι στον δείκτη αλλά μένει εκτός: διηπειρωτική, και το
# Numbeo την κατατάσσει στη Δυτική Ασία, όχι στον ευρωπαϊκό πίνακα τιμών.

CITY_EL = {
    "Amsterdam": "Άμστερνταμ", "Athens": "Αθήνα", "Barcelona": "Βαρκελώνη",
    "Basel": "Βασιλεία", "Berlin": "Βερολίνο", "Brussels": "Βρυξέλλες",
    "Budapest": "Βουδαπέστη", "Cologne": "Κολωνία", "Copenhagen": "Κοπεγχάγη",
    "Dublin": "Δουβλίνο", "Geneva": "Γενεύη", "Glasgow": "Γλασκώβη",
    "Hamburg": "Αμβούργο", "Helsinki": "Ελσίνκι", "Lisbon": "Λισαβόνα",
    "Liverpool": "Λίβερπουλ", "London": "Λονδίνο",
    "Luxembourg": "Λουξεμβούργο", "Madrid": "Μαδρίτη", "Manchester": "Μάντσεστερ",
    "Milan": "Μιλάνο", "Munich": "Μόναχο", "Oslo": "Όσλο", "Paris": "Παρίσι",
    "Stockholm": "Στοκχόλμη", "Vienna": "Βιέννη", "Zurich": "Ζυρίχη",
}

COUNTRY_EL = {
    "Austria": "Αυστρία", "Belgium": "Βέλγιο", "Denmark": "Δανία",
    "Finland": "Φινλανδία", "France": "Γαλλία", "Germany": "Γερμανία",
    "Greece": "Ελλάδα", "Hungary": "Ουγγαρία", "Ireland": "Ιρλανδία",
    "Italy": "Ιταλία", "Luxembourg": "Λουξεμβούργο", "Netherlands": "Ολλανδία",
    "Norway": "Νορβηγία", "Portugal": "Πορτογαλία", "Spain": "Ισπανία",
    "Sweden": "Σουηδία", "Switzerland": "Ελβετία", "United Kingdom": "Ηνωμένο Βασίλειο",
}

ISO2 = {
    "Austria": "AT", "Belgium": "BE", "Denmark": "DK", "Finland": "FI",
    "France": "FR", "Germany": "DE", "Greece": "GR", "Hungary": "HU",
    "Ireland": "IE", "Italy": "IT", "Luxembourg": "LU", "Netherlands": "NL",
    "Norway": "NO", "Portugal": "PT", "Spain": "ES", "Sweden": "SE",
    "Switzerland": "CH", "United Kingdom": "GB",
}

# Όπου το Numbeo ονομάζει αλλιώς την πόλη από ό,τι ο δείκτης.
NUMBEO_ALIAS: dict[str, str] = {}

BASE_FIELDS = [
    "city", "city_el", "country", "country_el", "iso2",
    "global_rank", "baseline_index", "net_salary_usd",
]
RENT_FIELDS = ["rent_1br_centre_usd", "rent_share_pct"]
TAIL_FIELDS = [
    "overworked_pct", "vacations_taken", "paid_parental_leave_days", "right_to_disconnect",
]


def load_prices() -> dict[str, dict[str, str]]:
    if not PRICES_CSV.exists():
        sys.exit(f"Λείπει το {PRICES_CSV.name}. Τρέξε πρώτα: python src/fetch_numbeo.py")
    with PRICES_CSV.open(encoding="utf-8") as handle:
        return {row["city_numbeo"]: row for row in csv.DictReader(handle)}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    prices = load_prices()

    with INDEX_CSV.open(encoding="utf-8") as handle:
        index_rows = list(csv.DictReader(handle))

    # Οι στήλες ενοικίου υπάρχουν μόνο αν το fetch_numbeo.py έτρεξε με --with-rent.
    has_rent = any(p.get("rent_1br_centre_usd") for p in prices.values())
    fields = BASE_FIELDS + (RENT_FIELDS if has_rent else []) + TAIL_FIELDS

    rows, missing = [], []
    for row in index_rows:
        city, country = row["city"], row["country"]
        if country not in EUROPEAN_COUNTRIES:
            continue

        price = prices.get(NUMBEO_ALIAS.get(city, city))
        if price is None or not price.get("net_salary_usd"):
            missing.append(city)
            continue

        salary = float(price["net_salary_usd"])
        rent = float(price["rent_1br_centre_usd"]) if price.get("rent_1br_centre_usd") else None

        record = {
            "city": city,
            "city_el": CITY_EL.get(city, city),
            "country": country,
            "country_el": COUNTRY_EL.get(country, country),
            "iso2": ISO2.get(country, ""),
            "global_rank": row["rank"],
            "baseline_index": row["baseline_index"],
            "net_salary_usd": f"{salary:.2f}",
            "overworked_pct": row["overworked_pct"],
            "vacations_taken": row["vacations_taken"],
            "paid_parental_leave_days": row["paid_parental_leave_days"],
            "right_to_disconnect": row["right_to_disconnect"],
        }
        if has_rent:
            record["rent_1br_centre_usd"] = f"{rent:.2f}" if rent else ""
            record["rent_share_pct"] = f"{100 * rent / salary:.1f}" if rent else ""
        rows.append(record)

    rows.sort(key=lambda r: int(r["global_rank"]))

    with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"{len(rows)} ευρωπαϊκές πόλεις -> {OUT_CSV.relative_to(ROOT)}")
    if missing:
        print(f"ΠΡΟΣΟΧΗ: χωρίς αντιστοίχιση στο Numbeo: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
