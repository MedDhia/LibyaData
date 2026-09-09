#!/usr/bin/env python3
"""
Check the built datasets against the accounting identities and published totals
that the sources themselves assert. Run after any extraction change.

Exit code 1 if a check that should hold exactly does not.
"""

import sys
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent.parent / "data" / "processed"
TOL = 0.15          # LYD millions, one decimal place of rounding
USD_TOL = 10.0

failures = []
notes = []


def check(name, residual, tol=TOL, exact=True):
    worst = float(residual.abs().max())
    bad = int((residual.abs() > tol).sum())
    status = "ok " if bad == 0 else ("FAIL" if exact else "note")
    print(f"  [{status}] {name:52s} max |resid| {worst:12,.2f}  breaches {bad}/{len(residual)}")
    if bad and exact:
        failures.append(f"{name}: {bad} breaches, worst {worst:,.2f}")
    elif bad:
        notes.append(f"{name}: {bad} breaches, worst {worst:,.2f}")


print("Central Bank of Libya, monetary statistics")
ms = pd.read_csv(OUT / "cbl_money_supply.csv")
mf = pd.read_csv(OUT / "cbl_money_supply_factors.csv")
mb = pd.read_csv(OUT / "cbl_monetary_base.csv")
bf = pd.read_csv(OUT / "cbl_monetary_base_factors.csv")
rr = pd.read_csv(OUT / "cbl_required_reserves.csv")

check("M1 = currency + demand deposits",
      ms.money_m1 - (ms.currency_in_circulation + ms.demand_deposits))
check("quasi money = time + saving deposits",
      ms.quasi_money - (ms.time_deposits + ms.saving_deposits))
check("M2 = M1 + quasi money", ms.money_supply_m2 - (ms.money_m1 + ms.quasi_money))
check("NFA total = central bank + commercial banks",
      mf.nfa_total - (mf.nfa_central_bank + mf.nfa_commercial_banks))
check("NDA total = treasury + other sectors + other items",
      mf.nda_total - (mf.net_claims_on_treasury + mf.claims_on_other_sectors
                      + mf.other_items_net))
check("M2 = NFA + NDA", mf.money_supply_m2 - (mf.nfa_total + mf.nda_total))
check("bank reserves = vault cash + deposits at CBL",
      mb.bank_reserves_total - (mb.cash_in_vault + mb.deposits_with_central_bank))
check("monetary base = currency + reserves + PE deposits",
      mb.monetary_base - (mb.currency_in_circulation + mb.bank_reserves_total
                          + mb.public_enterprise_demand_deposits))
check("base NDA = treasury + other + comm banks + other items",
      bf.nda_total - (bf.net_claims_on_treasury + bf.claims_on_other_sectors
                      + bf.claims_on_commercial_banks + bf.other_items_net))
check("monetary base = NFA + NDA", bf.monetary_base - (bf.net_foreign_assets + bf.nda_total))
check("reserve deposits total = demand + time", rr.deposits_total
      - (rr.demand_deposits + rr.time_deposits), exact=False)

print("\nCross-table agreement (source vintage differences, not errors)")
j = ms.merge(mf, on="date", suffixes=("_ms", "_mf"))
check("M2 agrees across the two money tables",
      j.money_supply_m2_ms - j.money_supply_m2_mf, exact=False)
j = ms.merge(mb, on="date", suffixes=("_ms", "_mb"))
check("currency agrees: money supply vs monetary base",
      j.currency_in_circulation_ms - j.currency_in_circulation_mb, exact=False)
j = mb.merge(bf, on="date", suffixes=("_mb", "_bf"))
check("monetary base agrees across its two tables",
      j.monetary_base_mb - j.monetary_base_bf, exact=False)
j = mf.merge(bf, on="date")
check("central bank NFA agrees across factor tables",
      j.nfa_central_bank - j.net_foreign_assets, exact=False)

print("\nCoverage")
for name, df in [("money supply", ms), ("money supply factors", mf),
                 ("monetary base", mb), ("monetary base factors", bf),
                 ("required reserves", rr)]:
    expected = pd.period_range(df.date.min()[:7], df.date.max()[:7], freq="M")
    got = pd.PeriodIndex(pd.to_datetime(df.date), freq="M")
    missing = sorted(set(expected) - set(got))
    status = "ok " if not missing else "FAIL"
    print(f"  [{status}] {name:52s} {len(df)} months, {len(missing)} gaps")
    if missing:
        failures.append(f"{name}: {len(missing)} missing months")

print("\nUses of foreign exchange")
bank = pd.read_csv(OUT / "cbl_fx_by_bank.csv")
purp = pd.read_csv(OUT / "cbl_fx_by_bank_purpose.csv")
for period in sorted(purp.period_end.unique()):
    year = int(period[:4])
    a = purp[(purp.period_end == period) & (purp.year == year)].value_usd.sum()
    b = bank[(bank.period_end == period) & (bank.year == year)].value_usd.sum()
    ok = abs(a - b) <= USD_TOL
    print(f"  [{'ok ' if ok else 'FAIL'}] {period}  by-purpose ${a:>16,.0f}  "
          f"by-bank ${b:>16,.0f}  diff ${a - b:>+8,.0f}")
    if not ok:
        failures.append(f"FX {period}: purpose and bank totals differ by {a - b:,.0f}")

print("\nConsumer prices")
cpi = pd.read_csv(OUT / "bsc_cpi_by_group.csv", dtype={"group_code": str})
gen = cpi[cpi.group_code == "00"]
dec23 = gen[(gen.year == 2023) & (gen.month == 12) & (gen.base_year == 2008)]
if len(dec23) == 1 and abs(float(dec23["index"].iloc[0]) - 296.9) < 0.05:
    print("  [ok ] December 2023 general index = 296.9, matching the BSC homepage")
else:
    failures.append("CPI: December 2023 does not match the BSC published 296.9")
    print("  [FAIL] December 2023 general index does not match the published 296.9")

for base, group in gen.groupby("base_year"):
    group = group.sort_values(["year", "month"])
    print(f"  [ok ] base {int(base)}=100: {len(group):3d} months "
          f"{group.date.iloc[0]} .. {group.date.iloc[-1]}")
unresolved = int(gen.base_year.isna().sum())
if unresolved:
    print(f"  [note] {unresolved} general-index months with an unresolved base year")
    notes.append(f"CPI: {unresolved} months with unresolved base year")
disputed = int(cpi.has_conflict.sum())
print(f"  [note] {disputed} observations flagged has_conflict "
      f"({int(gen.has_conflict.sum())} in the general index)")

print()
for n in notes:
    print(f"note: {n}")
if failures:
    print(f"\n{len(failures)} FAILURE(S):")
    for f in failures:
        print("  " + f)
    sys.exit(1)
print("All exact checks passed.")
