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
python3 scripts/extract_bsc_census_tables.py

git clone --depth 1 https://github.com/MedDhia/SatelliteImagery /tmp/satimg
python3 scripts/import_nighttime_lights.py --source /tmp/satimg

scripts/download_hdx_codab.sh
python3 scripts/download_hnec.py
python3 scripts/extract_hnec_polling_centres.py
python3 scripts/extract_hnec_municipal_baladiyat.py
python3 scripts/build_concordance.py

python3 scripts/download_opensanctions.py
python3 scripts/extract_opensanctions_libya.py
python3 scripts/export_libya_network.py

python3 scripts/download_gazette.py
python3 scripts/extract_gazette_appointments.py
python3 scripts/match_osm_places.py --places data/raw/hdx/hotosm_lby_populated_places.zip

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

### `bsc_census_2006_cells_<section>.csv.gz` — all 74 tables

Table 1 above is the census's first table. The volumes print 73 more, and these
files carry every figure in them: roughly a million, across eleven sections.

| File | Tables | Content |
|---|---|---|
| `..._households` | 1–9 | household size, composition, and the head's education, marital status and occupation |
| `..._age_sex` | 10–12 | population by age group and by single year of age, urban and rural |
| `..._non_libyans` | 13 | non-Libyan residents by country group, age and sex |
| `..._enrolment` | 14–16 | population aged 4–30 in education, by stage |
| `..._education` | 17–20 | population aged 10+ by educational attainment |
| `..._marital` | 21–28 | population aged 15+ by marital status, including polygamy |
| `..._manpower` | 29–36 | population aged 15+ by labour-force category |
| `..._occupation` | 37–45 | economically active 15+ by occupation |
| `..._activity` | 46–56 | economically active 15+ by branch of economic activity |
| `..._employment` | 57–68 | economically active 15+ by employment status |
| `..._housing` | 69–74 | dwelling type, water, cooking fuel, sanitation, lighting |

One row per printed figure:

| Column | Meaning |
|---|---|
| `shabiya_ar`, `shabiya_en` | the volume the figure came from |
| `table_no` | table number, 1–74, the same in every volume |
| `sheet` | continuation sheet number as printed. **Not reliable**: several volumes print "46-1" on four consecutive pages. Use `pdf_page` to separate sheets within a volume |
| `pdf_page` | page of the source PDF |
| `row_label_ar`, `row_label_en` | the row's stub, split by language. Age ranges are normalised to ascending `low-high` |
| `row_group_ar`, `row_group_en` | the outer stub, where a table has two levels — e.g. an education category subdivided into urban, rural and total. Empty for single-level tables |
| `column_index` | position of the column, counting from the right as printed |
| `column_label_ar`, `column_label_en` | the column's own heading, usually male, female or total |
| `column_group_ar`, `column_group_en` | the heading spanning that block of columns, e.g. the occupation or the economic activity |
| `column_kind` | `male`, `female`, `total`, `percent`, `count`, or empty |
| `value` | the figure as printed |
| `is_percentage` | 1 where the figure is a percentage rather than a count |

Roughly half the tables break down by mahalla, so `row_label_ar` joins to
`mahalla_ar` in the mahalla file. The rest cross-tabulate at shabiya level, and
their stub is a category: an age band, an occupation, a level of schooling.

**These are long, not wide.** Pivot on `row_label_ar` and `column_index` to get
a table back. Keep `column_index` in the key: several columns in one table can
share the label "total".

### `bsc_census_2006_table_index.csv`

One row per table: its section, the caption as printed in Arabic and English,
how many volumes and pages it was read from, how many figures, and its result on
the sex identity below. Read this first to find the table you want.

### `bsc_census_2006_table_headers.csv`

The header bands of each table exactly as extracted, by band and cell position.
The column labels above are derived from these; this file is here so a
researcher can check that derivation rather than take it on trust.

### How the 74 tables were validated

The tables have no single arithmetic spine, but most print male, female and
total columns. Every such triple is checked on every row, and the breach rate is
reported per table in the index. It runs well under a tenth of a percent, and
the breaches are misprints in the source rather than a systematic column
misalignment, which would break the identity everywhere at once.

Nothing was hard-coded per table. The reader finds the table number, learns
column positions from each page's own data rows, and takes column labels from
the header bands. That means a table whose layout it cannot resolve is skipped
and shows up as absent from the index, rather than being silently misread.

`volumes` in the index says how many of the 22 volumes each table was read
from. Most were read from all 22. Nine were read from fewer, and the shortfall
is in the source: those pages carry no printed table number, so they are
skipped rather than attributed to the neighbouring table. **Table 48** is the
extreme case, present in only 4 volumes; in the other 18 its pages print no
label at all.

The identity breaches concentrate in tables 25, 40, 41 and 45, at 1% to 4% of
their checks, against essentially zero elsewhere. Those are the densest
cross-tabulations, where the source stacks sub-rows about four points apart and
sets figures in narrow columns. A systematic column misalignment would breach
the identity on nearly every row of the affected table, not one in twenty-five,
so what remains is per-figure noise rather than a structural error. Treat
figures in those four tables with more caution than the rest, and use
`bsc_census_2006_table_headers.csv` to check any column reading that matters.

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

## Concordances

Three naming systems cover Libya's 22 first-level units, and no two agree:

| System | Names it uses | Where it matters |
|---|---|---|
| 2006 census | البطنان, الواحات, النقاط الخمس, وادي الحياة | every census table here |
| GADM 4.1 | Darnah, Surt, Misratah, Wadi ash Shati' — 7 of 22 match the census | the imported nighttime lights |
| COD-AB | names four units after their capital: Tobruk, Ejdabia, Zwara, Ubari | P-codes, and every humanitarian dataset on Libya |

### `concordance_shabiya.csv` — 22 units, all three systems

`shabiya_ar`, `shabiya_en`, `gadm_name`, `gadm_gid`, `codab_pcode`,
`codab_name_en`, `codab_name_ar`, `codab_renamed_for_capital`, both areas, and
the census population and mahalla count.

Each mapping is one-to-one and was checked by ranking units on area rather than
trusting name similarity: Spearman 0.985 against GADM, 0.988 against COD-AB.

**The units share names, not boundaries.** Libya reorganised after 2006. Against
the census, 9 of 22 GADM units agree within ±10% on area and 12 of 22 COD-AB
units do; national area differs by 3.6% from GADM and 3.6% from COD-AB. COD-AB
is the closer of the two to the census — it puts Tripoli at 842 km² against the
census's 835, where GADM has 2,435. Treat any join as matching units by
identity, not territory.

### `concordance_mahalla.csv` — 667 localities

| Column | Meaning |
|---|---|
| `mahalla_id` | stable key, matching the census file |
| `mahalla_ar` | name as printed in the census |
| `mahalla_key` | normalised join key: alef, ya and ta marbuta folded, definite article and spacing dropped, so مصراته and مصراتة agree |
| `shabiya_ar`, `shabiya_en`, `shabiya_gadm_name`, `shabiya_codab_pcode` | parent unit in all three systems |
| `name_unique_nationally`, `name_unique_in_shabiya` | 86 mahalla names recur somewhere in the country, 6 within their own shabiya |
| `codab_place_pcode`, `codab_place_en`, `codab_place_ar` | link to the COD-AB gazetteer, where one exists |
| `match_method` | `codab_gazetteer_same_shabiya` or `unmatched` |
| `baladiya_ar` | today's municipality, for the 402 mahallas where it could be established |
| `baladiya_source` | which route established it, or `ambiguous` or `not_established` — see below |
| `baladiya_candidates` | every municipality any route offers for this locality, before the shabiya constraint |
| `census_persons_2006`, `census_households_2006` | identifying attributes |

**Only 17 of the 667 carry an external link.** The COD-AB gazetteer holds 78
places for the whole country, and a link is only recorded where the parent
shabiya agrees as well as the name. Matching on name alone would have produced
far more links and many of them false: the census puts سوق الجمعة in Murqub
while the gazetteer places it in Tripoli, and الزهراء exists in both Jafara and
Wadi al Shatii.

### Mahalla to baladiya, and how it was established

**402 of 667 mahallas are mapped to a municipality, 5 are ambiguous, and 260
could not be established.** The census predates the 2013 reorganisation and no
published crosswalk relates its mahallat to today's baladiyat, so the mapping
comes from HNEC's polling-centre register instead, which lists every centre with
both its locality and its municipality.

The join is constrained to the shabiya, never made on name alone. Names repeat
across the country: سوق الجمعة is a Murqub mahalla in the census and a Tripoli
locality in the gazetteers; الزهراء exists in both Jafara and Wadi al Shatii.
HNEC does not state the shabiya, so it is inferred first — see
`concordance_baladiya.csv` below — and a mahalla is linked only to a baladiya
whose inferred shabiya is its own. A mahalla still matching more than one is
recorded `ambiguous` with its candidates listed rather than resolved to a guess.

`baladiya_source` says which route established each link, strongest first, so a
user who wants only the direct evidence can keep it and drop the rest:

| `baladiya_source` | Mahallas | What it means |
|---|---|---|
| `hnec_polling_centres_2021` | 305 | the 2021 register names this locality outright |
| `hnec_near_match` | 47 | the register names it one character away |
| `hnec_name_variant` | 42 | the register names the settlement the census name qualifies or is part of |
| `hnec_municipal_2024_2025` | 5 | only a 2024 or 2025 document names one of its polling centres |
| `hnec_city_2021` | 3 | the register names it as a city rather than a locality |
| `ambiguous` | 5 | more than one municipality survives the shabiya constraint |
| `not_established` | 260 | no route reaches it |

`hnec_name_variant` follows the census's own naming. A compound name is a part
of the place after the separator, so الشمالية / زوارة is in زوارة and الوسط \
جادو is in جادو; a name that is a settlement plus a direction is that
settlement, so قمينس الشرقية and قمينس الغربية are both in قمينس, الصابري الشرقي
and الصابري الغربي both in بنغازي. The words that name a part rather than a
place (المركز, الوادي, العين, القصبة, المدينة, and the directions themselves)
are never asked about on their own.

`hnec_near_match` is the weakest route and the one to drop first. Some register
localities were read through a font that drops letters, so سيدي حسين is printed
سيدي حسي and بنينة is بنينا. A census name is paired with a locality one edit
away only when the census name matches no locality exactly, the locality matches
no census name exactly, and each is the other's only candidate, which is what
stops الحمدية from absorbing the separate الحميدية. It is still a guess about
spelling, and 47 links rest on it.

Coverage after all routes is 60% and still uneven: Sabha and Kufra 100%, Jufra
86%, Nuqat al Khams 83%, against Benghazi 38%, Murzuq 33% and Al Wahat 20%.
Urban mahallat in the big cities were most often renamed or re-cut, so they
remain the least covered.

Spot checks land correctly: الظهرة, المدينة القديمة, المنشية and المنصورة map to
طرابلس المركز; عقبة بن نافع, الساحل and الجهاد to سوق الجمعة; قرقارش to حي الأندلس.

### `concordance_baladiya.csv` — 129 municipalities

Every municipality HNEC names, in the 2021 register or in the 2024 and 2025
documents, with the shabiya it was inferred to sit in, how many census localities
and polling centres back it, and whether the inference was unanimous. 21 are
named only by the later documents.

`shabiya_ar` is **inferred, not published**. A census mahalla whose name occurs
in only one shabiya is unambiguous evidence, so those vote — weighted by polling
centres — and each baladiya takes the shabiya with the most votes. 100 of 129 are
placed, 86 of them unanimously; the remaining 29 had no unambiguous census
locality to vote for them and are left blank.

`spellings` lists every spelling merged into the row. Two of the 24 register
documents were read through a font that drops and transposes letters, so the
same municipality is written طربق in one and طبرق in another, رست and سرت,
توكرا and توكره. Two spellings are treated as one municipality when they are at
most two characters apart **and** a polling centre or a locality is filed under
both, because a locality belongs to one municipality; distance alone would merge
درج into درنة. The surviving name is the best-attested spelling, preferring the
2025 file names, which are web page titles and never passed through a PDF font,
then the 2021 register, then the card-distribution statistics, which visibly
substitute Latin letters into Arabic words.

---

## Official Gazette — appointments

---

### `data/processed/gazette/` — 50 issues, 109 decisions, 16 appointments

The Official Gazette published by the House of Representatives, mirrored by
`scripts/download_gazette.py` and read by
`scripts/extract_gazette_appointments.py`. 50 issues, February 2023 to August
2026, 46 with a usable text layer and 4 page scans that are counted and skipped.

**This is one side of a split state, and it is a property of the data, not a
caveat.** الجريدة الرسمية, دولة ليبيا, ديوان مجلس النواب, printed "نُشرت بأمر
رئيس مجلس النواب", statutory basis Law 8 of 2011 as amended by Law 10 of 2022.
It began in January 2023 and records decisions of the House, its Presidency
Board and its Speaker, Supreme Constitutional Court judgments, decisions of the
House-appointed Council of Ministers, and public notices. It does **not** record
the Tripoli government's appointments. Every row carries `publishing_authority`,
and an analysis that reads this as a national appointments record will be
measuring the eastern institutions alone. The Government of National Unity's own
channel is a spam-injected placeholder; see `sources/access_notes.md`.

#### Reading order, which is the thing that breaks first

Each page's text layer comes out bottom line first, so lines are reversed per
page before anything else. Left alone, every decision appears to end before it
begins, and the signature date reads as the issue date.

#### `gazette_decisions.csv` — 109 decisions

A decision opens on a title line, `قرار <authority> رقم (73) لسنة 2024م`, with or
without the definite article, and is followed by a subject line beginning `بشأن`
or `في شأن`. Either can be missing: 15 of the 109 have no printed title, because
some issues set it as an image, and those keep the subject with the number left
empty.

Columns: `issue_id`, `issue_number`, `issue_year`, `issue_date`, `page`,
`decision_kind` (قانون or قرار), `issuing_body`, `decision_number`,
`decision_year`, `subject`, `act_ar`, `act_en`, `is_appointment`,
`signed_gregorian`, `signed_hijri`, `printed_in_issues`, `publishing_authority`,
`source_document`, `source_sha256`.

Two traps are handled and both are visible in the counts. Libyan statutory prose
is full of `بشأن` inside an article citing another law, so subject detection
stops once the articles begin; without that, one law becomes five. And the
gazette reprints: 21 of the 109 decisions appear in more than one issue,
sometimes as a corrected re-upload, so they are kept once with
`printed_in_issues` recording how often they were printed.

`signed_gregorian` is read from the last 14 lines of the block and only accepted
within four years of the issue. A decision's preamble cites the laws it rests
on, some from the 1960s, and the first date in the block is as likely to be one
of those: the check caught exactly that, a 1962 citation read as a 2023
signature.

#### `gazette_appointments.csv` — 39 rows, 16 decisions

An appointment is a decision whose subject performs one of nine acts. The fonts
transpose letters, printing تعيني for تعيين and جملس for مجلس, so matching runs
on the same fold the concordance uses rather than on the literal string.

| `act_en` | `act_ar` | Decisions |
|---|---|---|
| `committee_formation` | تشكيل | 8 |
| `assignment` | تكليف | 4 |
| `naming` | تسمية | 3 |
| `appointment` | تعيين | 1 |
| `secondment`, `promotion`, `removal`, `termination`, `renewal` | ندب, ترقية, إعفاء, إنهاء, تجديد | 0 |

What the 16 cover: the chairman of the Supreme Judicial Council, the head of the
Administrative Control Authority, the deputy head of the Audit Bureau, the chair
of the Wadi al Hareer special economic zone, the head and two deputies of the
Hajj and Umrah Authority, the members of the High National Elections Commission,
and eight parliamentary friendship and oversight committees.

Columns are the decision's, plus `person_name`, `person_key` and `person_line`.

**Names.** Taken from the honorific `السيد /` or `السيدة /`, alone or in a
numbered list. 29 of the 39 rows carry one; a decision naming nobody still
produces a row, so the count of appointment decisions is not distorted by name
extraction failing. Three repairs run first: a lone letter split off its word by
the font is rejoined (منصو ر becomes منصور, with an alef joining forward because
it starts the definite article); academic and military titles are stripped, so
د سلطنة مسعود and سلطنة مسعود are one person; and a span carrying an unmapped
glyph is discarded rather than half-read.

Role words are cut on the space-free concatenation, not on whole tokens, because
the fonts split those too: عض وا is عضوا and رئي سا is رئيسا, and cutting on
tokens alone leaves the role stuck to the name.

Two-letter fragments are **not** rejoined, because بن and أبو are real, so a few
names keep an internal split: إسماع يل for إسماعيل, السنو يس for السنوسي.
`person_key` exists for exactly that. It is the name folded and stripped of
spaces, so the split and unsplit forms join to each other, and it is what to
match on. `person_name` is what the page prints. `person_line` is the whole
line, so every extracted name can be checked against the source.

#### Geography: two of them, and they must not be conflated

Where a decision was signed is not where its office has authority. Both are
coded, separately.

**`issued_at`** is the city in the signature block, "صدر في مدينة بنغازي", with
`issued_at_shabiya_ar`, `_en` and `_pcode`. 58 of the 109 decisions carry one,
and 56 of those 58 are Benghazi: the House's Diwan signs from there. The other
two are the interesting rows, one from Tobruk and one from Tripoli. Among the 39
appointment rows, 35 are signed in Benghazi and 4 print no place.

**`office_shabiya_*`** is the territory the office covers, read from the subject,
and **almost nothing lands there. That is the finding, not a failure.** These
are national offices: the Supreme Judicial Council, the Audit Bureau, the
Administrative Control Authority, the elections commission. Of the 109
decisions, the subjects name no Libyan place at all.

**`office_scope`** codes the kind of office: `bilateral` for the three
parliamentary friendship committees, which are territorial only in naming
another country; `subnational` where a Libyan place resolves; `national`
otherwise. Across the 109 decisions that is 106 national and 3 bilateral, and
none subnational.

Matching runs against this repository's own concordance, 663 Arabic place names:
the 22 shabiyat, the 91 municipalities the concordance placed in one, and the
550 mahallas whose name occurs in exactly one shabiya. The 86 mahalla names that
repeat nationally are left out, because a name that could mean two provinces is
worse than no name.

Two rules keep it honest. Outside the 22 shabiyat, a place is accepted only when
a place-signalling word (بلدية, مدينة, منطقة, محلة, شعبية) stands immediately
before it; without that rule المحكمة العليا matches العليا, a mahalla in Jabal
al Gharbi, and six national court decisions acquire a false province. And a
phrase that fails the exact match is retried on its **anagram**, the letters of
the folded form sorted, because the fonts transpose letters inside a word: طبرق
prints as طربق and المغربية as املغربية, the same defect that gives جملس for
مجلس. Of the 658 anagram keys over the 663 names only three collide, and those
are excluded, so the fallback never chooses between two provinces.

#### `gazette_issues.csv` — 50 issues

`issue_number`, `issue_year` (the gazette counts in years since 2023, not
calendar years), `issue_date`, `published`, `pages_with_text`, `decisions`,
`appointments`, `read_by` (`text` or `scan_no_text_layer`), `source_sha256`.

---

## External data

---

### `data/external/nighttime_lights/`

The Libya subset of the LRCC-DVNL nighttime-lights analysis, 1992–2022, imported
from [MedDhia/SatelliteImagery](https://github.com/MedDhia/SatelliteImagery):
5 tables, 31 annual rasters and 321 figures. Per-shabiya sum of lights and light
density by year, national Gini and Theil series, the Theil decomposition, and
per-unit contributions.

**Different licence from the rest of this repository.** The boundaries are
GADM 4.1, which forbids commercial use and redistribution as boundary data; the
imagery is best read as CC BY-NC-ND 4.0. The upstream notice is copied to
`NOTICE.md` unchanged. Read that directory's README before using or citing any
of it — it also records why a lit pixel never dims, why 2014 is a sensor
handover, and why Libya's oil regions show the highest lights per head.

### `hnec_polling_centres_2021.csv` — 1,908 polling centres

HNEC's register as printed: `centre_code`, `centre_name`, `mahalla_ar`,
`city_ar`, `baladiya_ar`, plus `read_by` and the source document and its
SHA-256. Centre codes are unique nationally and 113 municipalities are named.

`read_by` is `text` for 22 of the 24 documents and `text_repaired` for two whose
embedded font maps every plain alef to alef-with-hamza-below, so البلدية arrives
as إلبلدية. The substitution is undone before parsing. A few words in those two
also carry letter-order noise that cannot be repaired, which the normalised join
key absorbs.

`hnec_locality_baladiya.csv` reduces this to the 949 distinct
locality-municipality pairs, with the polling centres behind each.

### `hnec_centre_baladiya_2024_2025.csv` — 754 statements, 564 centres

Two later HNEC collections restate the municipality of a subset of the same
polling centres, joined on `centre_code` rather than on any Arabic text:

* `municipal_2025`, eleven documents from October 2025, one per municipality
  holding a council election, with the municipality in the file name. Their text
  layer is scrambled, the embedded fonts reporting a different letter for almost
  every glyph, but the digits are unaffected. Each code is drawn twice, a
  shadow copy 0.06pt away, so two rows land on one baseline and interleave; a
  run of digits whose length is a multiple of five is de-interleaved by stride.
  Every one of the 360 codes recovered this way is a code the 2021 register
  already lists, which is the check on the method.
* `card_distribution`, the voter-card distribution statistics for the 2024 and
  2025 municipal rounds, whose centre name ends in the municipality in brackets.
  Their font substitutes Latin letters into some Arabic words, printing م اzتة
  for مصراتة, and naming the municipality is the whole point of the row, so a
  name that is not Arabic throughout is dropped, which loses 206 statements and
  leaves 394.

Columns: `centre_code`, `baladiya_ar`, `source_collection`, the register's
`mahalla_ar`, `city_ar` and `baladiya_2021_ar` for the same centre, and the
source document with its date and SHA-256.

HNEC also publishes 2,404 `قوائم الناخبين` voter lists naming individual
registered voters. Those are deliberately not downloaded or ingested.

### `data/external/sanctions/` — the Libyan subgraph, 702 nodes

The Libyan part of OpenSanctions, cut locally from the two global bulk
collections because no country subset is published: 1.9m PEP entities and 293k
sanctions entities, 2.24m lines, filtered in a five-pass stream by
`scripts/extract_opensanctions_libya.py`.

**Different licence from the rest of this repository: CC BY-NC 4.0**,
attribution required, non-commercial only. Read `NOTICE.md` in that directory
before using or citing any of it. `SOURCE.json` records the OpenSanctions export
version, the FollowTheMoney model version, and the upstream SHA-1 and local
SHA-256 of both bulk files.

**The global totals are not Libyan totals.** OpenSanctions holds 710,657
politically exposed persons and 293,095 sanctioned entities worldwide. Libya's
share is 702 nodes, of which 393 are people and 78 are Libyan officials. That is
the size of the thing, and no filtering choice makes it larger.

#### How an entity got in: `libya_link`

| `libya_link` | Nodes | What it means |
|---|---|---|
| `country_tagged` | 332 | the entity carries `ly` in country, nationality, citizenship, birthCountry, jurisdiction, mainCountry or registrationCountry |
| `tie_via_multicountry_hub` | 298 | reached only through a seed whose Libyan tag is one operational country among several |
| `accredited_to_libya` | 59 | holds a Libyan Position tagged `role.diplo`: a foreign ambassador posted to Libya, not a Libyan official |
| `tie_to_libya` | 13 | one edge from a Libya-specific entity |

Two of those need attention before use.

**Foreign ambassadors are not Libyan officials.** 64 of the 156 office spells in
the source are embassy postings to Tripoli: the ambassadors of the United
Kingdom, France, Spain, Germany, the United States, Pakistan, Hungary, Indonesia
and the Apostolic Nuncio. They hold a Position whose country is `ly`, so a naive
country filter counts them as Libyan PEPs. `is_libyan_official` is 1 only for a
person who holds a Libyan office that is not an embassy posting, or who carries a
governmental topic together with Libyan nationality. 78 people qualify.

**One hub imports a foreign network.** Sanctions lists record every country an
organisation operates in, so the Islamic Revolutionary Guard Corps arrives tagged
`ir;ly;sy`. Expanding one hop through it pulls in 298 mostly Iranian entities
that have nothing to do with Libya, and it is the single highest-betweenness node
in the graph by three orders of magnitude. Expansion therefore runs only through
**Libya-specific** seeds, whose country set is `ly` and nothing else, backed by a
degree cap of 25. Hub neighbours are kept, because dropping them would cut real
edges, and labelled `tie_via_multicountry_hub` so one filter removes them.

#### `libya_entities.csv` — 702 nodes

Identity and provenance: `entity_id`, `name`, `schema`, `libya_link`,
`libya_link_evidence`, `collection`, `is_target`, `datasets`, `source_urls`,
`first_seen`, `last_seen`.

Coding: `is_person`, `is_organisation`, `is_libyan_official`, `countries`,
`country_is_libya_only`, `topics` and `office_topics` verbatim, plus flat
indicators `is_pep`, `is_relative_or_associate`, `is_diplomat`, `is_judge`,
`is_oligarch`, `is_sanctioned`, `is_sanction_linked`, `is_counter_sanctioned`,
`is_export_controlled`, `is_person_of_interest`,
`is_head_of_state_or_government`, `is_criminal_designation`, and `gov_branch`.

FollowTheMoney puts `gov.executive` on the Position, not on the minister, so a
person row reads as untagged unless the office's topics are carried across. They
are: `office_topics` holds them, and the indicator columns are computed from the
union. 94 people carry `executive;national`, 22 `executive`, 10 `national`.

Attributes: `birth_date`, `death_date`, `birth_place`, `address_text`,
`position_text`, `aliases`, `offices_held`, `office_names`.

#### `libya_positions.csv` — 156 office spells

One row per person, office and spell: `person_id`, `position_name`,
`position_topics`, `is_foreign_posting`, `subnational_area`, `start_date`,
`end_date`, `status`. 78 distinct offices, the largest being Prime Minister of
Libya with 5 spells. 103 of the 156 spells carry a start date, running 1988 to
2026. This is the officeholder table, and the reason to want the
PEP collection at all.

#### `libya_edges.csv` and `libya_network.gexf` — 267 edges

An edge is a relationship OpenSanctions records between two entities: Family,
Associate, UnknownLink, Ownership, Directorship, Control, Employment,
Membership, Representation. Holding an office is not a tie between two people
and is not an edge; it is in `libya_positions.csv`.

`scripts/export_libya_network.py` writes the GEXF that Gephi, igraph, NetworkX
and Cytoscape read, with degree, connected component and exact betweenness
already on the nodes, and `libya_network_nodes.csv` with the same columns.

**The relational structure is thin, and that is the finding.** 432 of the 702
nodes have no edge at all. Of the 15 components, the largest is the 217-node
IRGC cluster described above; the largest genuinely Libyan component has 14
nodes, and the rest run 5, 5, 4, 4, 3, 3, 3 and six pairs. 184 of the 267 edges
are `UnknownLink`, meaning a source asserts a tie without naming it. Two are
Family. Anyone expecting to recover a Libyan elite network from sanctions data
should look at those numbers first: the Qadhafi cluster is the one real family
network in it.

#### Geography: 53 of 702 nodes

`shabiya_ar`, `shabiya_en`, `shabiya_pcode`, with `place_source` recording which
field answered and `place_matched_on` the token that matched. Four fields are
read, most direct first: `birthPlace`, the address on the entity, a linked
Address record, the `subnationalArea` of an office, and the office name.

Only 32 nodes resolve through a birthplace and 21 through an address. The reason
is simple: a sanctions listing gives a name, a birth date and a country, and
rarely a Libyan city. Tripoli takes 31 of the 53, then Nuqat al Khams 5, Derna 4,
Benghazi 4, Sirte 3, Jabal al Akhdar 2, Misrata 2, Marj 1. Fourteen shabiyat have
none.

Matching is against this repository's own concordance: the 22 shabiyat under
their census, GADM and COD-AB romanisations, the COD-AB gazetteer places the
mahalla concordance resolved, and a curated alias table for romanisations that
recur in sanctions lists (Misurata, Misratah, Tarabulus, Banghazi, Surt, Sebha,
Darnah, Tubruq). The alias table is in the script and every entry maps to a
shabiya the concordance already names. Anything unmatched is left empty rather
than guessed.

#### `libya_sanctions.csv` — 2,286 designations

One row per designation naming an entity in the node table: `authority`,
`authority_id`, `unsc_id`, `program`, `program_id`, `listing_date`, `start_date`,
`end_date`, `status`, `reason`. 44 authorities, led by OFAC with 274, the French
Trésor 169, the Swiss State Secretariat for Economic Affairs 162, the Belgian
Federal Public Service Finance 157 and the European Commission 157. The UN
Security Council accounts for 71.

The same person is designated repeatedly by different authorities, which is why
there are 2,286 records for 326 sanctioned nodes. Count designations to measure
international attention; count nodes to count people.

#### `libya_addresses.csv` — 390 records

Address records reached from the subgraph: `full`, `city`, `region`, `country`,
`latitude`, `longitude`, and the shabiya where one resolves. 45 of the 390 do.
Latitude and longitude are present only where the source supplied them; nothing
here is geocoded against an external service.

### `data/external/osm_places/mahalla_osm_anchors.csv`

A coordinate for each mahalla that could be matched to an OpenStreetMap place,
which is what allows a mahalla to be mapped or assigned to a future boundary
layer. 149 of 667 matched; 147 anchored to a point, 2 left ambiguous.

Matching is on the normalised Arabic name **and** the shabiya. Where several OSM
features share a name inside one shabiya they are treated as one place if they
lie within 5 km — the usual case of a settlement tagged as both a node and an
area, which accounts for 51 of the anchors — and as genuinely different places
otherwise, in which case the mahalla is left ambiguous rather than guessed.

`distance_to_shabiya_centroid_km` is for inspection only. Large values are
expected: several shabiyat exceed 70,000 km² and are long strips, so an edge
settlement can sit nearer a small neighbour's centroid. The authority for which
shabiya a point falls in is the COD-AB `adm2_pcode` already carried on the OSM
feature.

**ODbL.** OpenStreetMap is share-alike, so this file carries terms the rest of
the repository does not. It is kept out of `data/processed/` for that reason:
the concordance itself contains no OSM-derived content. See its `NOTICE.md`.

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
