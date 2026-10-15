#!/usr/bin/env python3
"""Render the charts used in README.md from data/inputs.csv and the model in backtest.py.

    python3 make_charts.py      # writes charts/*.png (needs matplotlib)
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from backtest import PERIODS, WEIGHTS, SENIOR_RATE, load_inputs, pool_return, waterfall  # noqa: E402

OUT = os.path.join(HERE, "charts")
os.makedirs(OUT, exist_ok=True)

# ---- style ---------------------------------------------------------------------------
ORANGE, DARK, MID, LIGHT, RULE, BG = "#F35233", "#2A1712", "#846964", "#D9CBC6", "#EDE7E4", "#FFFFFF"
for f in ("Inter", "DM Sans", "Helvetica Neue", "Arial"):
    if any(f == x.name for x in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = f
        break
plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG, "axes.edgecolor": RULE, "axes.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": RULE,
    "grid.linewidth": 0.6, "axes.axisbelow": True, "xtick.color": MID, "ytick.color": MID,
    "axes.labelcolor": MID, "text.color": DARK, "font.size": 11, "axes.titlesize": 14,
    "axes.titleweight": "semibold", "axes.titlelocation": "left", "axes.titlepad": 14,
    "xtick.major.size": 0, "ytick.major.size": 0, "legend.frameon": False,
})
LABELS = {"2020": "2020", "2021": "2021", "2022": "2022", "2023": "2023", "2024": "2024", "2025": "2025",
          "LTM": "Oct 25–\nSep 26"}


def f1(v):
    """One decimal, half-up (18.05 -> 18.1)."""
    return f"{v + 1e-9:.1f}"


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, name), dpi=200, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)


def footnote(ax, text):
    ax.text(0, -0.22, text, transform=ax.transAxes, fontsize=9, color=MID, va="top")


data, status = load_inputs()
rows = {}
for p in PERIODS:
    g = pool_return(data, p)
    net, paid, jr, cov = waterfall(g)
    rows[p] = dict(pool=g, net=net, senior=paid, junior=jr, cover=cov)
x = list(range(len(PERIODS)))
ticks = [LABELS[p] for p in PERIODS]

# 1. Junior return by year, with senior coupon and target ------------------------------
fig, ax = plt.subplots(figsize=(10, 5.2))
colors = [DARK if p == "LTM" else (LIGHT if int(p) <= 2022 else MID) for p in PERIODS]
bars = ax.bar(x, [rows[p]["junior"] for p in PERIODS], color=colors, width=0.62, zorder=3)
for b, p in zip(bars, PERIODS):
    ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.5, f"{f1(rows[p]['junior'])}%",
            ha="center", va="bottom", fontsize=11, fontweight="semibold", color=DARK)
ax.axhline(SENIOR_RATE, color=ORANGE, linewidth=2, zorder=4)
ax.text(-0.3, SENIOR_RATE + 0.45, "Phi Senior 6.5%, paid first", ha="left",
        color=ORANGE, fontsize=10.5, fontweight="semibold")
ax.axhline(15, color=MID, linewidth=0.9, linestyle=(0, (4, 4)), zorder=4)
ax.text(-0.3, 15.45, "15% junior target", ha="left", color=MID, fontsize=10)
ax.set_xticks(x, ticks)
ax.set_ylim(0, 25)
ax.set_yticks([0, 5, 10, 15, 20, 25], ["0", "5", "10", "15", "20", "25%"])
ax.set_title("Phi Junior return by period, today's mix on each platform's reported net returns")
footnote(ax, "Lighter bars (2020–22) use stand-ins for platforms that had not launched or had not yet published; "
             "see Data provenance.")
save(fig, "junior_by_period.png")

# 2. Senior cover ------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 4.2))
cov = [rows[p]["cover"] for p in PERIODS]
bars = ax.bar(x, cov, color=[ORANGE if c == min(cov) else DARK for c in cov], width=0.62, zorder=3)
for b, c in zip(bars, cov):
    ax.text(b.get_x() + b.get_width() / 2, c + 0.03, f"{c:.2f}x", ha="center", va="bottom", fontsize=11,
            fontweight="semibold", color=DARK)
ax.axhline(1.0, color=MID, linewidth=1, linestyle=(0, (4, 4)))
ax.set_xticks(x, ticks)
ax.set_ylim(0, 2.1)
ax.set_yticks([0, 0.5, 1.0, 1.5, 2.0], ["0", "0.5x", "1.0x", "1.5x", "2.0x"])
ax.set_title("Senior cover: net pool return ÷ senior cost (0.8 × 6.5%)")
footnote(ax, "Dashed line at 1.0x: net return exactly covers the senior coupon. Lowest cover 1.13x in 2020, when "
             "3-month T-bills averaged 0.36%.")
save(fig, "senior_cover.png")

# 3. Where the yield goes (LTM waterfall) -----------------------------------------------
p = "LTM"
g = rows[p]["pool"]
opex = 0.6
carry = g - opex - rows[p]["net"]
senior_cost = 0.8 * SENIOR_RATE
junior_share = rows[p]["net"] - senior_cost
steps = [("Pool earns", g, DARK), ("Running costs", -opex, LIGHT), ("Manager carry", -carry, LIGHT),
         ("To Phi Senior\n(80% × 6.5%)", -senior_cost, ORANGE), ("To Phi Junior\n(20% of vault)", -junior_share, MID)]
fig, ax = plt.subplots(figsize=(10, 5))
level = 0.0
for i, (name, v, c) in enumerate(steps):
    if i == 0:
        ax.bar(i, v, color=c, width=0.6, zorder=3)
        ax.text(i, v + 0.15, f"{v:.2f}%", ha="center", fontsize=11, fontweight="semibold")
        level = v
    else:
        ax.bar(i, -v, bottom=level + v, color=c, width=0.6, zorder=3)
        ax.plot([i - 1 + 0.3, i - 0.3], [level, level], color=MID, linewidth=0.8)
        ax.text(i, level + 0.15, f"{-v:.2f}", ha="center", fontsize=11, fontweight="semibold")
        level += v
ax.set_xticks(range(len(steps)), [s[0] for s in steps])
ax.set_ylim(0, 11)
ax.set_yticks([0, 2, 4, 6, 8, 10], ["0", "2", "4", "6", "8", "10%"])
ax.set_title("Where the yield goes, Oct 2025 – Sep 2026 inputs (% of vault assets a year)")
ax.text(3, junior_share + senior_cost / 2, "= 6.5% on\nthe senior", ha="center", va="center", color="white",
        fontsize=10, fontweight="semibold")
ax.text(4, junior_share / 2, f"= {f1(rows[p]['junior'])}% on\nthe junior", ha="center", va="center",
        color="white", fontsize=10, fontweight="semibold")
footnote(ax, f"Carry is 15% of net return above an 8% hurdle. The junior's {junior_share:.1f} points of pool return "
             f"land on 20% of the vault, so {f1(rows[p]['junior'])}% on the junior.")
save(fig, "yield_waterfall_ltm.png")

# 4. Platform returns, actual vs stand-in -----------------------------------------------
fig, ax = plt.subplots(figsize=(10, 5.2))
series = [("kilde", "Kilde", DARK), ("amttf", "TDB Medium-Term", ORANGE), ("esatf", "TDB ESATF", MID),
          ("helicap", "Helicap", "#B8391F"), ("tbill", "3-month T-bill", LIGHT)]
for key, name, c in series:
    ys = [data[key][p] for p in PERIODS]
    ax.plot(x, ys, color=c, linewidth=2, zorder=3)
    for i in range(len(PERIODS) - 1):
        seg_actual = status[key][PERIODS[i]] == "actual" and status[key][PERIODS[i + 1]] == "actual"
        if not seg_actual:
            ax.plot(x[i:i + 2], ys[i:i + 2], color=BG, linewidth=2.6, zorder=4)
            ax.plot(x[i:i + 2], ys[i:i + 2], color=c, linewidth=2, linestyle=(0, (2, 3)), zorder=5)
    act = [(i, y) for i, (p, y) in enumerate(zip(PERIODS, ys)) if status[key][p] == "actual"]
    ax.scatter([a[0] for a in act], [a[1] for a in act], color=c, s=28, zorder=6)
    ax.text(len(PERIODS) - 0.85, ys[-1] + {"helicap": 0.65, "esatf": -1.05, "amttf": -0.45}.get(key, 0.35), name, color=c, fontsize=10,
            fontweight="semibold")
ax.set_xticks(x, ticks)
ax.set_xlim(-0.4, len(PERIODS) + 0.4)
ax.set_ylim(0, 14)
ax.set_yticks([0, 2, 4, 6, 8, 10, 12, 14], ["0", "2", "4", "6", "8", "10", "12", "14%"])
ax.set_title("Platform net returns: solid with dots = published, dashed = stand-in")
footnote(ax, "Kilde, Helicap and the Huma buffer pay fixed-style coupons; the two TDB funds price off SOFR, "
             "which is why the pool and the junior track US rates.")
save(fig, "platform_returns.png")

# 5. Loss sensitivity --------------------------------------------------------------------
g = pool_return(data, "LTM")
losses = [i / 10 for i in range(0, 81)]
sen, jun = [], []
for L in losses:
    net, paid, jr, cov = waterfall(g, loss=L)
    sen.append(paid)
    jun.append(jr)
fig, ax = plt.subplots(figsize=(10, 4.8))
ax.plot(losses, jun, color=MID, linewidth=2.2, label="Phi Junior")
ax.plot(losses, sen, color=ORANGE, linewidth=2.6, label="Phi Senior")
ax.fill_between(losses, 0, sen, color=ORANGE, alpha=0.06)
ax.axvline(1.0, color=LIGHT, linewidth=1, linestyle=(0, (4, 4)))
ax.text(1.05, 17.2, "1% allowance\nin the forward view", color=MID, fontsize=9.5, va="top")
ax.set_xlabel("Vault-level credit losses on top of platform-reported returns, % of assets a year")
ax.set_xlim(0, 8)
ax.set_ylim(0, 20)
ax.set_yticks([0, 5, 10, 15, 20], ["0", "5", "10", "15", "20%"])
ax.legend(loc="upper right", fontsize=10.5)
ax.set_title("Loss sensitivity on today's inputs: the junior absorbs the first ~3.7 points, the senior holds to ~5")
footnote(ax, "Beyond that the junior's 20% of principal absorbs a further ~20 points of loss before the senior's "
             "principal is touched.")
save(fig, "loss_sensitivity.png")

# 6. Fixed vs floating senior ------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 4.8))
fixed = [rows[p]["junior"] for p in PERIODS]
floating = []
for p in PERIODS:
    sr = data["tbill"][p] + 2.6
    net, paid, jr, cov = waterfall(pool_return(data, p), senior_rate=sr)
    floating.append(jr)
w = 0.36
ax.bar([i - w / 2 for i in x], fixed, width=w, color=LIGHT, label="Junior with senior fixed at 6.5%", zorder=3)
ax.bar([i + w / 2 for i in x], floating, width=w, color=DARK, label="Junior with senior at T-bill + 2.6%", zorder=3)
for i, (a, b) in enumerate(zip(fixed, floating)):
    ax.text(i - w / 2, a + 0.4, f"{a:.0f}", ha="center", fontsize=9.5, color=MID)
    ax.text(i + w / 2, b + 0.4, f"{b:.0f}", ha="center", fontsize=9.5, color=DARK, fontweight="semibold")
ax.set_xticks(x, ticks)
ax.set_ylim(0, 29)
ax.set_yticks([0, 5, 10, 15, 20, 25], ["0", "5", "10", "15", "20", "25%"])
ax.legend(loc="upper left", fontsize=10, ncol=2)
ax.set_title("A floating senior would have kept the junior at 13.6–20% in every period")
footnote(ax, "Option for a later series: index the senior coupon to the 3-month T-bill so rate swings land on the "
             "senior, not the junior.")
save(fig, "fixed_vs_floating.png")

print("wrote", sorted(os.listdir(OUT)))
