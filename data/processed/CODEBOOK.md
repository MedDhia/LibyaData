# Codebook

All files in `data/processed/` are UTF-8 CSV with a header row. Missing values
are empty, never zero and never a sentinel. Figures are reproduced as published:
no deflation, no currency conversion, no rebasing, no interpolation of gaps.

Rebuild everything from source with:

```bash
scripts/download_cbl.sh
python3 scripts/extract_cbl_monetary.py
python3 scripts/extract_cbl_fx.py

python3 scripts/harvest_bsc_catalogue.py
python3 scripts/download_bsc_pdfs.py
python3 scripts/extract_bsc_cpi.py
python3 scripts/extract_bsc_census.py

python3 scripts/validate.py
```

`validate.py` re-checks every accounting identity and published total described
below. It exits non-zero if a check that should hold exactly stops holding.

Each extraction writes a `*_source_manifest.json` recording the SHA-256 of every
PDF it read, so a rebuild can be checked against the exact files used here.

---

## Central Bank of Libya — monetary statistics

Source: <https://cbl.gov.ly/en/monetary-and-banking/>. Monthly, **millions of
Libyan dinars**, observations dated to the last calendar day of the month.
Coverage 2004-01 to 2026-04 (268 months) in every table, with no gaps.

### `cbl_money_supply.csv`

| Column | Meaning |
|---|---|
| `date`, `year`, `month` | end of month |
| `currency_in_circulation` | notes and coin outside banks |
| `demand_deposits` | includes public enterprise deposits held at the CBL |
| `money_m1` | `currency_in_circulation + demand_deposits` |
| `time_deposits` | includes resident foreign-currency deposits |
| `saving_deposits` | |
| `quasi_money` | `time_deposits + saving_deposits` |
| `money_supply_m2` | `money_m1 + quasi_money` |

### `cbl_money_supply_factors.csv`

Counterpart decomposition of M2.

| Column | Meaning |
|---|---|
| `nfa_central_bank`, `nfa_commercial_banks`, `nfa_total` | net foreign assets |
| `net_claims_on_treasury` | negative when the Treasury is a net depositor |
| `claims_on_other_sectors` | |
| `other_items_net` | residual |
| `nda_total` | net domestic assets |
| `money_supply_m2` | `nfa_total + nda_total` |

### `cbl_monetary_base.csv`

| Column | Meaning |
|---|---|
| `currency_in_circulation` | |
| `cash_in_vault`, `deposits_with_central_bank` | components of bank reserves |
| `bank_reserves_total` | their sum |
| `public_enterprise_demand_deposits` | |
| `monetary_base` | sum of the three preceding aggregates |

### `cbl_monetary_base_factors.csv`

| Column | Meaning |
|---|---|
| `net_foreign_assets` | central bank only |
| `net_claims_on_treasury`, `claims_on_other_sectors`, `claims_on_commercial_banks`, `other_items_net` | |
| `nda_total` | their sum |
| `monetary_base` | `net_foreign_assets + nda_total` |

### `cbl_required_reserves.csv`

| Column | Meaning |
|---|---|
| `demand_deposits`, `time_deposits`, `deposits_total` | commercial bank deposits at the CBL |
| `reserve_requirements` | required |
| `excess_reserves` | `deposits_total - reserve_requirements` |

### `cbl_monetary_long.csv`

The five tables stacked: `date`, `year`, `month`, `table`, `variable`,
`value_million_lyd`. 8,844 observations. Use this for tidy-data workflows.

### `cbl_capital_adequacy.csv`

Annual, percent. `year`, `period` (`annual`, or `Q1` for the partial 2026
observation), `tier1_capital_adequacy_pct`, `total_capital_adequacy_pct`.
2004–2026, 23 observations.

---

## Central Bank of Libya — uses of foreign exchange

Source: <https://cbl.gov.ly/en/uses-of-foreign-exch/>. **US dollars.**

Each release is **cumulative from 1 January** to `period_end`. Releases are not
monthly flows: to obtain the flow between two dates, difference two releases.
Twelve releases are covered, `period_end` 2025-06-30 to 2026-07-31.

### `cbl_fx_by_bank.csv`

Foreign exchange purchased from the CBL, by bank. Each release reports the
current year and the equivalent period of the prior year, so `year` distinguishes
the two.

`period_end`, `year`, `bank`, `rank`, `value_usd`, `market_share_pct`.

### `cbl_fx_by_bank_purpose.csv`

Same universe split by purpose. `purpose` takes `letters_of_credit`,
`miscellaneous_transfers`, `personal_purposes`, `merchants_cards`. A blank
`value_usd` means the source printed "-" (the bank was not operating in that
period), which is distinct from a printed zero.

**Reconciliation.** For every release, this table sums to `cbl_fx_by_bank`
within $5, and both match the totals stated in the CBL's own narrative text.

### `cbl_fx_lc_by_firm.csv`

Accepted letter-of-credit coverage requests by beneficiary firm. Roughly 3,000
named companies per release. `period_end`, `rank`, `firm_name`, `value_usd`,
plus the provenance columns below.

This is firm-level access to hard currency at the official rate, named. It has
no equivalent in any international dataset on Libya.

### `cbl_fx_lc_by_goods.csv`, `cbl_fx_lc_by_country_origin.csv`, `cbl_fx_lc_by_country_beneficiary.csv`, `cbl_fx_foreign_transfers.csv`

The same allocations aggregated by goods or service category, by country of
origin of the goods, by country of the payment beneficiary, and (in three
releases) foreign salary transfers.

### Provenance columns on every appendix file

| Column | Meaning |
|---|---|
| `sector` | `private`, `public`, or `unspecified` — some releases split the appendices by sector, others do not |
| `section_seq` | 1 unless the same heading appeared more than once in one release |
| `source_section_label` | the heading exactly as printed |

**Read `source_section_label` before pooling.** Section headings are not stable
across releases and at least one release repeats a heading over two different
tables. See "Known source defects" below.

### Relationship to the aggregate tables

The appendix totals do not equal the published letters-of-credit figure. For the
2025 full-year release the appendices sum to \$16,090,030,018 against a stated
letters-of-credit total of \$15,681,022,797. The firm, goods and country
appendices all sum to the same figure as each other, so this is a difference of
concept in the source — *requests accepted* against *foreign exchange used* —
not an extraction error. Do not force them to agree.

---

## Bureau of Statistics and Census — consumer prices

Source: <https://bsc.ly/economic_statistics/>.

### `bsc_cpi_by_group.csv`

Monthly consumer price index by COICOP division.

| Column | Meaning |
|---|---|
| `year`, `month`, `date` | reference month |
| `group_code` | COICOP division, `00` = general index. **Read as text**: leading zeros are significant |
| `group_name` | English label, harmonised across releases |
| `index` | index value |
| `weight` | the group's weight in the basket, as printed for that base |
| `base_year` | the base the figure is on |
| `mom_change_pct` | month-on-month change, where the source printed one |
| `annual_average` | the year's average, where the source printed one |
| `base_year_source` | `stated` if the document names its base, `matched` if the base was established by matching figures against a document that does |
| `has_conflict` | 1 where another BSC document prints a different figure for the same month, group and base |
| `family` | `A` full-year table, `B` monthly comparison report |
| `source_document`, `source_sha256` | the file the figure came from |

**The series is not continuous across base years.** The BSC rebased from
2008=100 to 2024=100 with effect from January 2025, and changed the basket
weights (food and beverages moved from 38.8 to 40.39). Figures on different
bases are different series: filter on `base_year`, and splice only by computing
growth rates within each base, never by joining levels.

The BSC also publishes a parallel 2003=100 series on a different commodity
classification. It is not comparable to either of the above and is excluded.

Coverage: 103 months on the 2008 base (2015-01 to 2024-12), 12 months on the
2024 base (2025-01 to 2025-12), and 7 months whose base could not be
established, which carry an empty `base_year`.

**Base years are never assumed.** Many monthly reports omit the base. Rather
than guessing, the extraction matches such a document against documents that do
state a base: where both print the same figure for the same month and group, the
document is on that base, and resolution repeats so documents chain through each
other. Where no match exists the base is left empty. `base_year_source` records
which route was taken.

**External check.** December 2023 on the 2008 base extracts as 296.9, matching
the figure the BSC states on its own homepage.

### `bsc_cpi_source_conflicts.csv`

Where two BSC documents print different values for the same month, group and
base, this records both and names the documents. The extraction keeps the first
and reports the disagreement rather than silently choosing.

---

## Bureau of Statistics and Census — 2006 population census

Source: <https://bsc.ly/demog_statist/>, 22 volumes, one per shabiya.

The 2006 general census is Libya's last full enumeration. Table 1 of each volume
gives, for every mahalla (locality), households and resident population split by
the nationality of the household and the nationality of the individual. Table 3,
reprinted in every volume, gives each shabiya's area, population and density.

### `bsc_census_2006_mahalla.csv` — 667 mahallas

| Column | Meaning |
|---|---|
| `mahalla_id` | stable key, `<shabiya>-<printed order>`. **Use this, not the name**: three mahalla names repeat within their own shabiya |
| `shabiya_ar`, `shabiya_en` | first-level unit, Arabic authoritative |
| `mahalla_ar` | locality name as printed, in logical order |
| `libyan_hh_households` | households headed by Libyans |
| `libyan_hh_libyans`, `libyan_hh_non_libyans`, `libyan_hh_persons` | people resident in those households, by their own nationality, and the total |
| `non_libyan_hh_*` | the same four figures for non-Libyan households |
| `households`, `libyans`, `non_libyans`, `persons` | all households, and all residents |
| `identity_failures` | count of the six accounting identities the printed row breaks |
| `imputed_cells` | count of cells the source left blank that its own arithmetic determines uniquely |
| `page` | page of the source PDF |
| `source_document`, `source_sha256` | the volume the row came from |

### `bsc_census_2006_shabiya.csv` — 22 shabiyat

The total row printed in each volume, plus `area_km2` and `density_per_km2` from
Table 3, and `volume_title_ar` because four volume titles differ from the formal
shabiya name (the volume titled المنطقة الغربية is النقاط الخمس; طبرق is البطنان;
الشاطئ is وادي الشاطئ; مصراتة is printed مصراته in Table 3).

### `bsc_census_2006_checks.csv`

Every identity failure and every reconciliation, passing or failing.

### How the figures were validated

Nothing here rests on trusting a page number or a caption. Each row carries six
accounting identities, and those identities are what *locate* Table 1 in the
first place, since its page and caption differ between volumes.

- All six identities hold on 666 of 667 mahallas.
- 21 of 22 volumes: the mahallas sum exactly to the volume's own printed total.
- All 22 volumes: the printed total matches that shabiya's row in Table 3.
- All 22 copies of Table 3 extract identically.
- The 22 shabiya totals sum to **5,657,692**, Libya's published 2006 census
  population, and the areas to **1,676,198 km²**, both exactly.

### Reading the Arabic

The volumes are typeset in Arabic presentation forms in visual order, so text
must be converted before use; `scripts/arabic_text.py` does this. The order of
operations matters: a lam-alef ligature is one glyph standing for two letters and
must be reversed *before* being expanded. Expanding first silently swaps the two
letters — الجلاء becomes الجالء — and the result still reads as plausible Arabic,
so the corruption is invisible on inspection. Every place name containing
lam-alef would be wrong.

---

## Source inventory

### `data/raw/bsc/bsc_catalogue.csv`

Every publication reachable through the BSC sitemaps: 248 documents across
economic, demographic, vital and social statistics, each with its page URL,
Arabic title, document URL, format and reference years. Useful in its own right
as a bibliography of Libyan official statistics.

---

## Known source defects

Recorded rather than corrected, except where noted.

| Where | Defect | Handling |
|---|---|---|
| CBL money supply factors, 2013-12 | Net domestic assets printed as `85899.1-`, a right-to-left rendering artifact for a negative number | Corrected to −85,899.1. Confirmed by the identity M2 = NFA + NDA, which then holds exactly |
| CBL assets and liabilities, 2023-03 | Same trailing-minus artifact | Same handling |
| CBL required reserves, 2019-09 | Demand plus time deposits (71,865.6) does not equal the printed total (72,208.2) | Left as printed. The total is consistent with the excess reserves figure, so a component is misprinted |
| CBL, currency in circulation | The money supply and monetary base tables disagree in 4 of 268 months (largest 72.8m LYD) | Both kept. Different publication vintages |
| CBL, central bank net foreign assets | The two factor tables disagree in 21 of 268 months, including a constant 2,004.2m LYD gap across all of 2018 | Both kept. This is a vintage difference in the CBL's own tables and should be reported, not averaged |
| CBL FX appendices, Aug/Sep/Oct 2025 releases | The heading "According to Country of Origin - Private Sector" appears twice over two different tables; comparison with releases that label the sections properly indicates the second is the beneficiary-country table | Not reassigned. Tagged `section_seq=2` with the verbatim heading so the ambiguity is visible |
| BSC CPI | Base year printed four different ways across documents, and often not at all | All four patterns are read; documents that state none are resolved by matching, or left with an empty base year |
| BSC CPI, 9 months in 2018, 2019, 2022, 2023 | Two BSC documents print different figures for the same month, group and base — largest gap 560.6 index points, in tobacco | Both kept. The first is written to the dataset with `has_conflict = 1`, the alternative and both document names to `bsc_cpi_source_conflicts.csv` |
| 2006 census, المرقب, الفاسي | Total persons printed as 50; the row's own components give 2,910, and the shabiya total confirms it | Left as printed, flagged in `identity_failures` and named in the checks file. This single misprint is the entire 2,860 gap between the mahalla sum and the shabiya totals |
| 2006 census, three cells | Cells left blank where the value is zero, in النقاط الخمس and المرقب | Filled from the identities that determine them uniquely, counted in `imputed_cells` |
| BSC CPI, 2026 | Only March and April 2026 are published, with no overlap onto the 2024-base series, so their base cannot be established. The level (113.9, 116.0) is far above December 2025 (102.8) | Kept with an empty `base_year`. Do not splice onto the 2024 base without confirming with the BSC |
