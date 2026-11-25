import sys

print(sys.version.split()[0])

from collections import deque
from math import isfinite


def replay(rows, policy="average", window=3,
           fee=0.001, start=0, initial=1000.0,
           deposits=None, staged_months=None):
    """Use (date, open, close) rows in time order."""
    if (len(rows) < 2 or not 0 <= start < len(rows)-1
            or window < 1 or not 0 <= fee < 1
            or initial < 0):
        raise ValueError("Check the dates and settings.")
    if policy not in {"average", "hold", "staged"}:
        raise ValueError("Unknown policy.")

    recent = deque(maxlen=window)
    cash, shares = initial, 0.0
    ledger = []
    prior = None
    deposits = deposits or {}
    staged_dates = {
        date[:7]: date for date, _, _ in
        reversed(rows[start:-1])
    }
    months = list(staged_dates)[::-1]
    if staged_months is not None:
        allowed = set(months[:staged_months])
        staged_dates = {m: d for m, d in staged_dates.items()
                        if m in allowed}
    tranche = initial / (staged_months or len(staged_dates))

    for i, (date, opening, close) in enumerate(rows):
        if (prior is not None and date <= prior
                or not isfinite(opening)
                or not isfinite(close)
                or min(opening, close) <= 0):
            raise ValueError("Check the price rows.")
        target = (len(recent) == window
                  and recent[-1] > sum(recent) / window)
        recent.append(close)
        prior = date
        if i < start:
            continue

        deposit = deposits.get(date, 0.0)
        if deposit < 0:
            raise ValueError("Deposits must be nonnegative.")
        cash += deposit
        action, charge = "", 0.0

        if i < len(rows) - 1:
            if policy == "average" and not target:
                if shares:
                    value = shares * opening
                    charge = value * fee
                    cash += value - charge
                    shares, action = 0.0, "Sell"
            else:
                budget = cash
                if policy == "staged":
                    first = staged_dates.get(date[:7])
                    budget = (min(cash, tranche)
                              if date == first else 0.0)
                if budget > 1e-9:
                    value = budget / (1 + fee)
                    charge = budget - value
                    shares += value / opening
                    cash -= budget
                    action = "Buy"

        ledger.append({
            "date": date, "open": opening,
            "deposit": deposit, "action": action,
            "fee": charge, "cash": cash, "shares": shares,
            "value": cash + shares * opening,
        })
    return ledger


def score(ledger, initial=1000.0):
    """Drawdown and return on a flow-adjusted account."""
    peak, index, worst = 1.0, 1.0, 0.0
    previous = initial
    for row in ledger:
        deposit = row["deposit"]
        before_trade = row["value"] + row["fee"]
        before_deposit = before_trade - deposit
        if previous > 0:
            index *= before_deposit / previous
        if before_trade > 0:
            index *= row["value"] / before_trade
        peak = max(peak, index)
        worst = max(worst, 1 - index / peak)
        previous = row["value"]
    return {
        "value": ledger[-1]["value"],
        "return": index - 1,
        "drawdown": worst,
        "orders": sum(bool(r["action"]) for r in ledger),
    }

from csv import reader
from io import StringIO

july_text = """2022-07-01,272.22,275.32
2022-07-05,271.60,280.04
2022-07-06,280.42,281.83
2022-07-07,282.64,287.86
2022-07-08,285.03,288.22
2022-07-11,285.81,282.07
2022-07-12,283.32,279.33
2022-07-13,273.83,278.76
2022-07-14,276.16,279.75
2022-07-15,282.74,284.83
2022-07-18,287.61,282.42
2022-07-19,286.04,291.10
2022-07-20,291.52,295.72
2022-07-21,296.18,299.96
2022-07-22,299.04,294.70
2022-07-25,294.73,293.03
2022-07-26,291.33,287.27
2022-07-27,291.83,299.41
2022-07-28,299.19,302.34
2022-07-29,303.87,307.85
"""
july = [(d, float(o), float(c))
        for d, o, c in reader(StringIO(july_text))]

import json
from datetime import datetime
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from datetime import timezone

URL = (
    "https://query2.finance.yahoo.com/v8/finance/chart/QQQ"
    "?period1=1606780800&period2=1704067200&interval=1d"
)


def read_prices(document):
    chart = document["chart"]["result"][0]
    if chart["meta"]["symbol"] != "QQQ":
        raise ValueError("The response is not QQQ.")
    try:
        clock = ZoneInfo("America/New_York")
    except ZoneInfoNotFoundError:
        # Daily US opening timestamps remain same-day in UTC.
        clock = timezone.utc
    quotes = chart["indicators"]["quote"][0]
    return [
        (datetime.fromtimestamp(t, clock).date().isoformat(),
         round(o, 2), round(c, 2))
        for t, o, c in zip(chart["timestamp"], quotes["open"],
                           quotes["close"], strict=True)
        if o is not None and c is not None
    ]


def fetch_prices():
    request = Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        return read_prices(json.load(response))

def compare(rows, window=20, fee=0.001):
    start = next(i for i, row in enumerate(rows)
                 if row[0] >= "2021-01-01")
    policies = ("hold", "staged", "average")
    results = {
        p: replay(rows, p, window, fee, start)
        for p in policies
    }
    return results


def monthly_case(rows, window=20, fee=0.001):
    start = next(i for i, row in enumerate(rows)
                 if row[0] >= "2021-01-01")
    flows = {}
    months = set()
    for date, _, _ in rows[start:-1]:
        month = date[:7]
        if month not in months:
            months.add(month)
            flows[date] = 100.0
    return {
        p: replay(rows, p, window, fee, start, 0, flows)
        for p in ("hold", "average")
    }

from pathlib import Path

cache = Path("qqq_history.json")
rows = []
try:
    if not cache.exists():
        request = Request(URL, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=20) as response:
            raw = response.read()
    else:
        raw = cache.read_bytes()
    candidate = read_prices(json.loads(raw))
    if (len(candidate) != 775
            or candidate[0][0] != "2020-12-01"
            or candidate[-1][0] != "2023-12-29"):
        raise ValueError("Unexpected date coverage.")
    if not cache.exists():
        cache.write_bytes(raw)
    rows = candidate
    print(len(rows), rows[0], rows[-1])
except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
    print("Historical data unavailable:", error)
    print("Exercises from the short July case still work.")

start = 1000
end = 1050

gain = end - start
return_percent = gain / start * 100

print("Dollar gain:", gain)
print("Return (%):", round(return_percent, 2))

closes = [100, 102, 104, 98, 97, 99]
window = 3

for i in range(window - 1, len(closes)):
    recent = closes[i - window + 1:i + 1]
    average = sum(recent) / window
    target = "Fund" if closes[i] > average else "Cash"
    print(i + 1, closes[i], round(average, 2), target)

cash = 1000
fee_percent = 1
fee = fee_percent / 100

invested = cash / (1 + fee)
ending_cash = invested * (1 - fee)

print(f"Ending balance: ${ending_cash:,.2f}")

toy = [
    ("01", 99, 100), ("02", 100, 102),
    ("03", 102, 104), ("04", 103, 98),
    ("05", 97, 97), ("06", 98, 99),
    ("07", 101, 104), ("08", 105, 106),
]
result = replay(toy, fee=0, start=3)
for row in result:
    print(row["date"], row["action"],
          round(row["value"], 2))

benchmark = replay(toy, "hold", fee=0, start=3)
for name, ledger in [("Rule", result),
                     ("Hold", benchmark)]:
    report = score(ledger)
    print(name, round(report["value"], 2),
          report["orders"])

prices = [25, 20, 40]
deposit = 100
regular_shares = 0
waiting_cash = 0

for price in prices:
    regular_shares += deposit / price
    waiting_cash += deposit

waiting_shares = waiting_cash / prices[-1]
print("Regular purchases:", regular_shares * prices[-1])
print("Wait until last date:", waiting_shares * prices[-1])

scenarios = {
    "Rising": [100, 105, 110, 115],
    "Falling": [100, 95, 90, 85],
    "Reversing": [100, 105, 100, 105],
}

for name, opens in scenarios.items():
    hold = 1000 * opens[-1] / opens[0]
    rule = 1000 * opens[1] / opens[0]
    rule *= opens[-1] / opens[2]
    print(name, round(rule, 2), round(hold, 2))

trial = replay(july, fee=0.001, start=3)
for row in trial:
    if row["action"]:
        print(row["date"], row["action"],
              round(row["value"], 2))

for fee in (0.001, 0.005):
    for policy in ("average", "hold"):
        ledger = replay(july, policy, fee=fee, start=3)
        report = score(ledger)
        print(fee, policy, round(report["value"], 2),
              round(report["drawdown"] * 100, 2))

if rows:
    results = compare(rows)
    for name, ledger in results.items():
        report = score(ledger)
        print(name, round(report["value"], 2),
              report["orders"])
else:
    print("Run the optional historical data setup first.")

if rows:
    for name, ledger in monthly_case(rows).items():
        report = score(ledger, initial=0)
        deposits = sum(r["deposit"] for r in ledger)
        print(name, round(deposits, 2),
              round(report["value"], 2))
else:
    print("Run the optional historical data setup first.")

if rows:
    for fee in (0.001, 0.005):
        history = compare(rows, fee=fee)["average"]
        print(fee, round(score(history)["value"], 2))
else:
    print("Run the optional historical data setup first.")

from datetime import date, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode


def load_through(cutoff):
    end = date.fromisoformat(cutoff) + timedelta(days=1)
    if end < date(2024, 1, 1):
        raise ValueError("Use 2023-12-31 or later.")
    query = urlencode({
        "period1": 1606780800,
        "period2": int(datetime.combine(
            end, datetime.min.time(), timezone.utc).timestamp()),
        "interval": "1d",
    })
    path = Path(f"qqq_through_{cutoff}.json")
    if path.exists():
        data = path.read_bytes()
    else:
        endpoint = "https://query2.finance.yahoo.com/v8/finance/chart/QQQ"
        request = Request(f"{endpoint}?{query}",
                          headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=20) as response:
            data = response.read()
    prices = [row for row in read_prices(json.loads(data))
              if row[0] <= cutoff]
    dates = [row[0] for row in prices]
    if (not dates or dates[0] != "2020-12-01"
            or dates != sorted(set(dates))):
        raise ValueError("Check the source dates.")
    if not path.exists():
        path.write_bytes(data)
    return prices


def compare_period(prices, first, last):
    rows = [row for row in prices if row[0] <= last]
    start = next((i for i, row in enumerate(rows)
                  if row[0] >= first), len(rows))
    if start < 20 or start >= len(rows) - 1:
        raise ValueError("Need 20 prior closes and two scored opens.")
    return {
        policy: score(replay(
            rows, policy, window=20, fee=0.001, start=start,
            staged_months=36))
        for policy in ("hold", "staged", "average")
    }

cutoff = "2025-12-31"
prices = load_through(cutoff)
periods = [
    ("Original", "2021-01-01", "2023-12-31"),
    ("Extension", "2024-01-01", cutoff),
    ("Full period", "2021-01-01", cutoff),
]
for label, first, last in periods:
    if last < "2024-01-03" and label == "Extension":
        continue
    print(label, first, last)
    for policy, result in compare_period(
            prices, first, last).items():
        print(policy, round(result["value"], 2),
              round(result["drawdown"] * 100, 2),
              result["orders"])

cutoff = "2025-12-31"
prices = load_through(cutoff)
result = compare_period(prices, "2021-01-01", cutoff)
print(round(result["hold"]["value"], 2))
