"""
generate_price_history.py

Reads a CSV with columns: product_name, start_range, end_range
Outputs a 30-day price history CSV with realistic market simulation.

Usage:
    python generate_price_history.py input.csv [output.csv]

If no output file is specified, it defaults to price_history_30d.csv
"""

import sys
import csv
import random
import math
from datetime import date, timedelta

# ── Simulation parameters ──────────────────────────────────────────────────────

DAYS = 30
BASE_DATE = date.today()

# Volatility regimes — chosen randomly per product
REGIMES = {
    "stable": {"daily_vol": 0.003, "drift": 0.0001},  # e.g., mainstream retail
    "moderate": {"daily_vol": 0.008, "drift": 0.0002},  # e.g., mid-market goods
    "volatile": {"daily_vol": 0.018, "drift": -0.0001},  # e.g., luxury / collectibles
    "trending_up": {"daily_vol": 0.006, "drift": 0.0012},
    "trending_down": {"daily_vol": 0.006, "drift": -0.0010},
}


def gbm_path(mid_price: float, regime: dict, days: int, seed: int) -> list[float]:
    """Geometric Brownian Motion path."""
    rng = random.Random(seed)
    mu = regime["drift"]
    sigma = regime["daily_vol"]
    prices = [mid_price]
    for _ in range(days - 1):
        shock = rng.gauss(0, 1)
        daily_return = math.exp((mu - 0.5 * sigma**2) + sigma * shock)
        prices.append(prices[-1] * daily_return)
    return prices


def add_market_events(prices: list[float], seed: int) -> list[float]:
    """Inject occasional realistic events: flash sales, spikes, weekend dips."""
    rng = random.Random(seed + 999)
    result = list(prices)
    n = len(result)

    # Random flash sale (1–2 days, –5% to –12%)
    if rng.random() < 0.4:
        day = rng.randint(3, n - 5)
        duration = rng.randint(1, 2)
        discount = rng.uniform(0.05, 0.12)
        for i in range(day, min(day + duration, n)):
            result[i] *= 1 - discount

    # Occasional price spike (supply shock / demand surge, +4% to +9%)
    if rng.random() < 0.3:
        day = rng.randint(5, n - 3)
        spike = rng.uniform(0.04, 0.09)
        result[day] *= 1 + spike

    return result


def spread_around(mid: float, spread_pct: float, rng: random.Random):
    """Return (low, high) around a midpoint with a random intra-day spread."""
    half = mid * spread_pct * rng.uniform(0.5, 1.5)
    return round(mid - half, 2), round(mid + half, 2)


def simulate_product(
    product_name: str, start_range: float, end_range: float, seed: int
):
    """Return list of dicts for all 30 days of a single product."""
    mid = (start_range + end_range) / 2
    spread_pct = (end_range - start_range) / mid / 2  # intra-day spread as % of mid

    regime = random.Random(seed).choice(list(REGIMES.values()))
    path = gbm_path(mid, regime, DAYS, seed)
    path = add_market_events(path, seed)

    rng = random.Random(seed + 1234)
    rows = []
    for i, daily_mid in enumerate(path):
        day = BASE_DATE + timedelta(days=i)
        lo, hi = spread_around(daily_mid, spread_pct, rng)
        # Keep within ±30% of original band — realistic floor/ceiling
        floor = start_range * 0.70
        ceiling = end_range * 1.30
        lo = max(lo, floor)
        hi = min(hi, ceiling)
        if lo > hi:
            lo, hi = hi, lo
        rows.append(
            {
                "date": day.isoformat(),
                "product_name": product_name,
                "start_range": lo,
                "end_range": hi,
            }
        )
    return rows


def main():
    input_file = "/Users/rachitdas/Desktop/csci-6234/Project/api/dataset.csv"
    output_file = "output.csv"

    products = []
    with open(input_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            products.append(
                {
                    "product_name": row["product_name"].strip(),
                    "start_range": float(row["start_range"]),
                    "end_range": float(row["end_range"]),
                }
            )

    if not products:
        print("No products found in input file.")
        sys.exit(1)

    print(f"Simulating 30 days of prices for {len(products)} product(s)...")

    all_rows = []
    for idx, p in enumerate(products):
        seed = hash(p["product_name"]) % (2**31) + idx  # deterministic per product
        rows = simulate_product(
            p["product_name"], p["start_range"], p["end_range"], seed
        )
        all_rows.extend(rows)

    # Transpose: products as rows, dates as columns
    from collections import defaultdict

    dates = sorted(set(r["date"] for r in all_rows))
    by_product = defaultdict(lambda: {"start": {}, "end": {}})
    for row in all_rows:
        by_product[row["product_name"]]["start"][row["date"]] = row["start_range"]
        by_product[row["product_name"]]["end"][row["date"]] = row["end_range"]

    fieldnames = ["product_name", "price_type"] + dates
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in products:
            name = p["product_name"]
            for price_type in ("start", "end"):
                row = {"product_name": name, "price_type": price_type}
                row.update(by_product[name][price_type])
                writer.writerow(row)

    print(
        f"Done. {len(products) * 2} rows × {len(dates)} date columns written to '{output_file}'"
    )


if __name__ == "__main__":
    main()
