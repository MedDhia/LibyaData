# Libyan-Domiciled Data Sources

Phase 1 of the LibyaData project: an inventory of data produced and published **inside Libya**, by
Libyan institutions, on Libyan-hosted domains. International sources (World Bank, IMF, UN OCHA,
ACLED, IOM DTM) are deliberately out of scope here and will be catalogued separately, because the
purpose of this phase is to establish what the Libyan state and Libyan society say about themselves
before any external re-coding is applied.

Machine-readable version: [`libyan_sources.csv`](libyan_sources.csv) — 40 institutions, 18 fields.
Access and retrieval problems are documented in [`access_notes.md`](access_notes.md).

All entries were probed on **2026-09-09**. The `access_status` and `verified_2026_09_09` fields
record what was actually observed, not what the institution claims.

---

## What exists, ranked by research value

### 1. Bureau of Statistics and Census (BSC) — https://bsc.ly

The national statistical office, and the only Libyan institution with a genuine multi-topic
statistical programme. Its output is the spine of any harmonized Libya dataset.

Confirmed holdings, enumerated from the site's own sitemaps:

| Series | Coverage observed | Level |
|---|---|---|
| General population census results | 2006, published per city/municipality — Tripoli, Benghazi, Misrata, Sabha, Zawiya, Jabal al-Gharbi, Jufra, Shati, Kufra, Marj, Murqub, Wahat, Derna, Sirte, Tobruk, Ghat, Murzuq, Nalut, Wadi al-Hayat | municipality |
| Consumer price index | monthly, running to Dec 2023 (index 296.9, base 2008=100) | national |
| Foreign trade summaries | annual volumes for 2005, 2008, 2010–2016, plus a compiled time series and a 2010–2016 trends volume | national, partner, commodity |
| Import statistics | multiple separate volumes | national |
| Vital statistics | 2007, 2008, 2011, plus a compiled 2012–2022 series | national |
| Labour force / employment and unemployment survey | 2012, 2013, 2022 | national |
| Household income and expenditure survey | 2022/2023 preliminary results | national |
| MICS (Multiple Indicator Cluster Survey) | final report published; MICS7 results announced Oct 2025, extended national report Aug 2026 | national, region |
| Libyan National Family Health Survey | 2014 | national |
| Maternal and neonatal nutrition survey | national | national |
| ICT indicators | national | national |
| Statistical yearbook (الكتاب الإحصائي) | 2023 edition | national |
| Labour market dynamics report | thematic | national |

The 2006 census disaggregated to municipality is the single most valuable item here: it is the last
full enumeration, and it gives a subnational baseline that almost every downstream Libyan dataset
implicitly relies on.

**Retrieval note.** The publication listing pages (`/our-versions/`, `/blog/`) render client-side
and return nothing to a plain HTTP client. The catalogue is instead reachable through
`https://bsc.ly/wp-sitemap.xml`, which indexes five publication post types:
`economic_statistics`, `demog_statist`, `vital-administrative`, `social_statistics`, and `m-chart`.
Harvest from the sitemap, not the front end.

### 2. Central Bank of Libya (CBL) — https://cbl.gov.ly

The best-maintained Libyan data publisher, and the only one with continuous series long enough for
time-series work. Fully bilingual (`/en/` mirror).

Confirmed series, with observed start years taken from the file names themselves:

- Monetary base, money supply, required reserves, consolidated commercial bank balance sheet,
  currency denominations issued, capital adequacy ratio for commercial banks — each published as a
  **2004 to current** run, latest observed April 2026 / Q1 2026.
- Quarterly Economic Bulletin — observed 2022 Q2 through 2026 Q1, in both Arabic and English editions.
- Uses of foreign exchange by commercial banks — cumulative year-to-date releases, observed monthly
  from Jan 2025 through Feb 2026. This is effectively an import-financing series and has no
  substitute elsewhere.
- Balance of payments, foreign trade statistics (including a dedicated 2019–2022 foreign trade
  report), annual reports, financial stability reports, GDP statistics, statistical handbook.
- Daily official exchange rates (USD, EUR, GBP, CAD and others).

Everything is PDF. Converting the 2004– monetary tables into tidy CSV is the highest-return
extraction task in this whole project.

### 3. High National Elections Commission (HNEC) — https://hnec.ly

The authoritative source for Libyan electoral data: results, voter registration statistics,
candidate lists, constituency definitions and polling centre lists, covering the 2012 GNC election,
the 2014 House of Representatives and Constitution Drafting Assembly elections, and the three
phases of the 2024–2026 municipal elections.

**This is the largest untapped source for Libyan political science**, and also the hardest to
reach: the site sits behind a Sucuri WAF that blacklists datacenter IP ranges outright (block ID
`BLACK02`). It loads normally in an ordinary browser. See `access_notes.md`.

### 4. House of Representatives — https://parliament.ly

Legislative output, in a structure that is unusually amenable to systematic coding:

- Official Gazette (الجريدة الرسمية), organised by legislative year (first through fourth).
- Plenary session records under `/category/الجلسات/`.
- Statements archived by year, with separate category pages for 2015, 2016, 2017, 2018, 2019, 2020,
  2021, 2022 and 2023.
- Standing committee membership lists.

Combined with the GNU decisions at https://pm.gov.ly, this supports a legislative- and
decree-output dataset for the post-2014 institutional split.

### 5. Ministry of Economy and Trade — https://economy.gov.ly

Underused. Carries a `/statistics/` section, a `/reports/` section, `/import-export/`
documentation, an `/investment-map/`, registers of joint companies and commercial agencies, and —
most usefully — **`/daily-rates/`**, a daily commodity price feed. That gives an independent
high-frequency price series to validate the BSC's monthly CPI against, which matters because the
CPI has published gaps.

### 6. National Centre for Disease Control (NCDC) — https://ncdc.org.ly

EWARN early-warning surveillance, COVID-19 epidemiological situation reports, the Multisectoral NCD
Strategy 2026–2030, and scientific and administrative reports. Note that some documents are hosted
on Google Drive rather than the NCDC domain, so links rot; mirror on ingest.

### 7. Libyan Audit Bureau — https://audit.gov.ly

The annual report of the Audit Bureau is the most detailed public account of Libyan state spending
and institutional performance that exists — spending by ministry and state company, staffing,
irregularities. For political economy work on rent distribution and state capacity it has no
substitute. The domain returns HTTP 200 with an empty body to scripted clients, so retrieval is
manual or archival.

### 8. Libyan News Agency (LANA) — https://lana.gov.ly

Not a statistical source, but a systematically harvestable one. Articles are addressed as
`post.php?lang=ar&id=NNNNNN` with sequential IDs (around 365,000 as of September 2026), in both
Arabic and English. That structure makes the full state newswire archive available as a text corpus
for work on official framing, elite signalling, and event extraction.

---

## Sources that exist but publish little or nothing

Reachable, institutionally relevant, but currently thin on data. Worth monitoring rather than
ingesting:

- **Ministry of Finance** (mof.gov.ly) — has `/reports/`, `/transparency_report/` and a monthly
  report section, but the actual release cadence needs checking against archived snapshots.
- **Ministry of Labour** (labour.gov.ly) — decisions and legislation only; no employment statistics.
  Labour data comes from BSC.
- **Ministry of Education** (moe.gov.ly) — policy and examination regulations, no enrolment figures.
  Its National Centre for Examinations (nec.moe.gov.ly) publishes examination results, which are
  the closest available proxy for education outcomes below the national level.
- **National ID Project** (nid.gov.ly) — a service portal, not a publisher. Worth flagging anyway:
  the civil registry behind it links civil status, criminal record, passport, health, education and
  employment files. It is the backbone administrative database of the Libyan state and none of it
  is publicly released.
- **Libyan Capital Market Authority** (lcma.gov.ly) — the register of licensed companies is a usable
  firm-level list.
- **National Oil Corporation** (noc.ly) — publishes current production and a daily benchmark price
  panel on the homepage, but the `/reports/` section exposes almost no downloadable tables.
  Production figures reach the public mainly through press releases, so building an NOC production
  series means parsing announcements rather than downloading data.

## Sources that are dead or compromised

- **Libyan Stock Market** (lsm.gov.ly) — 301-redirects to a bare IP (`41.208.106.218`) that serves
  nothing. Treat as defunct. Use LCMA and CBL for capital-market data.
- **Tax Authority** (tax.gov.ly) — **the site is compromised.** Its homepage carries injected SEO
  spam linking to gambling and unrelated commercial domains. Do not treat any document served from
  this host as authenticated without independent corroboration. Flagged 2026-09-09.

---

## What this inventory tells us about the data landscape

Four structural features shape any harmonization work that follows.

**The 2011 and 2014 breaks are visible in the data itself, not only in the politics.** BSC foreign
trade volumes run 2005–2016 with gaps; vital statistics jump 2011 to a compiled 2012–2022 series;
the labour force survey appears in 2012, 2013, then not again until 2022. The CBL is the only
publisher with a continuous 2004– run. Any panel built from Libyan sources will have a structural
hole around 2011 and thinning coverage after 2014, and that pattern needs to be documented as a
property of the data rather than silently interpolated.

**Institutional duplication after 2014 is not yet reflected in this inventory.** The eastern
parallel institutions — the Bayda-based central bank branch, the eastern government, the eastern
NOC claim — did not resolve to reachable domains in this sweep. Where two authorities issue
competing figures for the same quantity, the repository will need to store both with an issuing
authority field rather than pick one. This is a gap to close in Phase 2.

**Almost nothing is machine-readable.** Of 40 institutions, one (LANA) is systematically harvestable
by design, two more (LCMA registers, Libya Observer tags) are partially structured, and the rest
publish PDF or client-side-rendered HTML. Extraction, not collection, is where the work is.

**Access is fragile in a specific and correctable way.** Seven of the 40 sites block datacenter IPs
or return 403 to scripted clients, and they include three of the most valuable (HNEC, the Ministry
of Health, the Social Security Fund). This is a WAF configuration problem, not a data availability
problem — the material is public and loads in a normal browser. It does mean that a naive scraper
run from a cloud host will silently conclude that Libyan election data does not exist.

---

## Coverage by research domain

| Domain | Libyan sources available | Assessment |
|---|---|---|
| Demography | BSC census 2006, vital statistics 2007–2022, MICS, family health survey | Usable, one full census only |
| Prices and inflation | BSC CPI monthly, MoET daily commodity rates | Usable, with gaps in the CPI |
| Trade | BSC 2005–2016, CBL foreign trade, MoET import/export | Usable |
| Money and banking | CBL, 2004–2026 continuous | Strong |
| Public finance | Audit Bureau annual reports, MoF | Rich content, hard retrieval |
| Labour | BSC LFS 2012, 2013, 2022 | Thin |
| Elections | HNEC 2012–2026 | Rich content, WAF-blocked |
| Legislation and executive action | HoR gazette and sessions, GNU decisions | Strong, unstructured |
| Health | NCDC surveillance, MoH | Moderate |
| Education | NEC exam results, MoE policy | Thin |
| Energy | NOC and subsidiaries | Thin relative to sector importance |
| Firms and markets | LCMA register, MoET agency registers, LISCO, LIA | Thin |
| Text corpora | LANA, Libya Observer, Libya Herald, Al-Marsad, Alwasat | Strong |
