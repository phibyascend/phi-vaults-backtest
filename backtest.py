#!/usr/bin/env python3
"""Phi Vaults backtest: 80/20 senior/junior waterfall over a book of regulated
private-credit and trade-finance platforms, 2020 to Sep 2026.

Standard library only. Run:  python3 backtest.py
Reads  data/inputs.csv   (every input with its status: actual or stand-in, and source)
Writes results/results.csv, results/sensitivity.csv
"""
import csv
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PERIODS = ["2020", "2021", "2022", "2023", "2024", "2025", "LTM"]  # LTM = Oct 2025 - Sep 2026

# Target mix (share of vault assets)
WEIGHTS = {"kilde": 0.25, "esatf": 0.30, "helicap": 0.20, "amttf": 0.15, "buffer": 0.10}

# Vault terms
OPEX = 0.6          # % of assets a year: administrator, audit, directors, custody, oracle, hosting
SENIOR_SHARE = 0.8  # Phi Senior share of the vault
SENIOR_RATE = 6.5   # fixed coupon, % a year
CARRY = 0.15        # manager performance fee on net return above the hurdle
HURDLE = 8.0        # % a year; nothing earned below it


def load_inputs(path=os.path.join(HERE, "data", "inputs.csv")):
    data = defaultdict(dict)
    status = defaultdict(dict)
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            data[row["series"]][row["period"]] = float(row["value_pct"])
            status[row["series"]][row["period"]] = row["status"]
    return data, status


def waterfall(gross, opex=OPEX, loss=0.0, senior_share=SENIOR_SHARE,
              senior_rate=SENIOR_RATE, carry=CARRY, hurdle=HURDLE):
    """All figures in % of vault assets a year.

    gross   platform returns, weighted, as each platform reports them (after its own fees and losses)
    loss    extra vault-level loss allowance (0 in the backtest: platform returns already include losses)
    Returns (net, senior_paid, junior_return, senior_cover).
    """
    pre = gross - opex - loss
    net = pre - carry * max(0.0, pre - hurdle)
    senior_paid = min(senior_rate, net / senior_share)               # senior is paid first, up to its coupon
    junior = (net - senior_share * senior_paid) / (1 - senior_share)  # junior keeps the rest, absorbs shortfall
    cover = net / (senior_share * senior_rate)                        # net return / senior cost
    return net, senior_paid, junior, cover


def pool_return(data, period, weights=WEIGHTS, override=None):
    override = override or {}
    return sum(w * override.get(s, data[s][period]) for s, w in weights.items())


def main():
    data, status = load_inputs()
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)

    # ---- Base case -------------------------------------------------------------------
    rows = []
    print("Base case: fixed 6.5% senior, 0.6% opex, 15% carry above 8%, 80/20")
    print(f"{'period':6s} {'pool':>6s} {'net':>6s} {'senior':>7s} {'junior':>7s} {'cover':>6s}  stand-ins")
    for p in PERIODS:
        g = pool_return(data, p)
        net, paid, jr, cov = waterfall(g)
        standins = [s for s in WEIGHTS if status[s][p] == "stand-in"]
        rows.append({"period": p, "pool_pct": round(g, 2), "net_pct": round(net, 2),
                     "senior_paid_pct": round(paid, 2), "junior_pct": round(jr, 2),
                     "senior_cover_x": round(cov, 2), "stand_in_series": " ".join(standins)})
        print(f"{p:6s} {g:6.2f} {net:6.2f} {paid:7.2f} {jr:7.2f} {cov:5.2f}x  {' '.join(standins)}")
    with open(os.path.join(HERE, "results", "results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ---- Forward view (today's inputs, 1% loss allowance) ----------------------------
    g = pool_return(data, "LTM", override={"buffer": 7.75})
    _, _, jr1, _ = waterfall(g, loss=1.0)
    _, _, jr0, _ = waterfall(g, loss=0.0)
    print(f"\nForward view on LTM inputs: pool {g:.2f}%  junior {jr1:.1f}% with a 1% loss allowance "
          f"({jr0:.1f}% without)")

    # ---- Sensitivities -----------------------------------------------------------------
    sens = []

    def record(name, period, g, loss=0.0, senior_rate=SENIOR_RATE):
        net, paid, jr, cov = waterfall(g, loss=loss, senior_rate=senior_rate)
        sens.append({"test": name, "period": period, "pool_pct": round(g, 2), "senior_rate_pct": senior_rate,
                     "senior_paid_pct": round(paid, 2), "junior_pct": round(jr, 2), "senior_cover_x": round(cov, 2)})
        return net, paid, jr, cov

    print("\nS1  Kilde stand-in for 2020-21 replaced with alternatives")
    for alt_name, alt in (("Kilde = 8%", 8.0), ("Kilde = ESATF", None)):
        for p in ("2020", "2021"):
            k = data["esatf"][p] if alt is None else alt
            g = pool_return(data, p, override={"kilde": k})
            net, paid, jr, cov = record(f"S1 {alt_name}", p, g)
            print(f"    {alt_name:14s} {p}: pool {g:5.2f}  senior paid {paid:4.2f}  junior {jr:6.2f}  cover {cov:4.2f}x")

    print("\nS2  Helicap pays nothing for a year (0% instead of 8%)")
    g = pool_return(data, "LTM", override={"helicap": 0.0})
    net, paid, jr, cov = record("S2 Helicap 0%", "LTM", g)
    print(f"    LTM: pool {g:5.2f}  senior paid {paid:4.2f}  junior {jr:6.2f}  cover {cov:4.2f}x")

    print("\nS3  Kilde loses 15% of face in one year (Kilde's own Mar 2026 stress case)")
    g = pool_return(data, "LTM") - WEIGHTS["kilde"] * 15.0
    net, paid, jr, cov = record("S3 Kilde -15% face", "LTM", g)
    print(f"    LTM: pool {g:5.2f}  senior paid {paid:4.2f}  junior {jr:6.2f}  cover {cov:4.2f}x")

    print("\nS4  Floating senior at 3-month T-bill + 2.6% (rate swings hit the senior, not the junior)")
    for p in PERIODS:
        sr = data["tbill"][p] + 2.6
        g = pool_return(data, p)
        net, paid, jr, cov = record("S4 floating senior", p, g, senior_rate=sr)
        print(f"    {p:5s} senior {sr:5.2f}  junior {jr:6.2f}")

    print("\nS5  Vault-level loss allowance on top of platform returns (LTM inputs)")
    g = pool_return(data, "LTM")
    for loss in (0.0, 1.0, 2.0, 3.0, 3.7, 5.0):
        net, paid, jr, cov = record(f"S5 loss {loss}%", "LTM", g, loss=loss)
        print(f"    loss {loss:3.1f}%: senior paid {paid:4.2f}  junior {jr:6.2f}")

    with open(os.path.join(HERE, "results", "sensitivity.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(sens[0].keys()))
        w.writeheader()
        w.writerows(sens)


if __name__ == "__main__":
    main()
