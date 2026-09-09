# LibyaData

A harmonized, documented data repository on Libya for social science research.

Libyan data is not so much missing as scattered, undocumented, and published in formats that resist
analysis. The national statistical office, the central bank, the elections commission and the audit
bureau all publish real material — as PDFs, on sites that render client-side, behind firewalls that
block automated access, across an institutional landscape that has been split since 2014. The
purpose of this repository is to collect that material, document its provenance and its gaps, and
release it in tidy, analysis-ready form.

## Status

**Phase 2 — extraction.** Nineteen datasets built from the two highest-value
Libyan sources, with a validation suite. See
[`data/processed/CODEBOOK.md`](data/processed/CODEBOOK.md).

| Dataset | Coverage | Rows |
|---|---|---|
| CBL money supply, and its counterparts | 2004-01 – 2026-04, monthly | 268 each |
| CBL monetary base, and its counterparts | 2004-01 – 2026-04, monthly | 268 each |
| CBL required reserves | 2004-01 – 2026-04, monthly | 268 |
| CBL monetary series, stacked long | 2004-01 – 2026-04 | 8,844 |
| CBL capital adequacy | 2004 – 2026, annual | 23 |
| CBL foreign exchange by bank | 12 releases, 2025-06 – 2026-07 | 544 |
| CBL foreign exchange by bank and purpose | 10 releases | 1,840 |
| CBL letters of credit by beneficiary firm | 11 releases, ~3,000 firms each | 22,830 |
| CBL letters of credit by goods, origin, beneficiary country | 12 releases | 5,265 |
| BSC consumer price index by COICOP division | 2015-01 – 2026-04, monthly | 1,175 |
| **BSC 2006 census, by mahalla** | Libya's last full enumeration | 667 |
| BSC 2006 census, by shabiya, with area and density | 22 first-level units | 22 |
| BSC publication catalogue | all four statistical domains | 248 |

Everything is reproducible from source: `scripts/` downloads the PDFs, extracts
the tables and records the SHA-256 of every file read. `python3
scripts/validate.py` re-checks the results.

**Phase 1 — source identification.** Complete for Libyan-domiciled sources.

40 Libyan institutions inventoried and probed on 2026-09-09:

- [`sources/libyan_sources.csv`](sources/libyan_sources.csv) — machine-readable inventory, 18 fields
  per institution covering sector, data domains, geographic level, temporal coverage, formats,
  languages, update frequency and verified access status.
- [`sources/README.md`](sources/README.md) — narrative guide, ranked by research value, with the
  confirmed holdings of each major source and an assessment of coverage by research domain.
- [`sources/access_notes.md`](sources/access_notes.md) — what is blocked, what is broken, what is
  compromised, and how to reproduce the reachability check.

## What the data shows

Every one of the ten accounting identities inside the Central Bank's monetary
tables holds exactly across all 268 months, and the foreign exchange tables
reconcile to within \$5 of the totals the CBL states in its own text. December
2023 consumer prices extract as 296.9, the figure the BSC publishes itself.
These are not incidental checks: they are the evidence that the column mapping
is right, and `scripts/validate.py` re-runs them.

Three findings came out of building it.

**The Central Bank's own tables disagree with each other.** Central bank net
foreign assets differ between the two factor tables in 21 of 268 months,
including a constant 2,004.2m LYD gap running through every month of 2018.
Currency in circulation differs between the money supply and monetary base
tables in 4 months. These are publication vintages that were never reconciled.
Both versions are kept, and the disagreements are listed rather than averaged.

**The consumer price index breaks in January 2025.** The BSC rebased from
2008=100 to 2024=100 and changed the basket weights. The two are separate series
and the dataset keeps them apart with a `base_year` column. Most monthly reports
never state their base at all, so the extraction establishes it by matching
figures against documents that do, records which route was taken, and leaves the
base empty where no match exists rather than guessing.

**The 2006 census reconciles to the digit.** The 22 shabiya totals sum to
5,657,692 and the areas to 1,676,198 km², both exactly the published national
figures, and every volume's total matches its row in the national summary table
reprinted across all 22 volumes. One discrepancy survives, and it is the
source's: المرقب/الفاسي prints 50 total residents where its own components give
2,910. That single misprint is the whole 2,860 gap between the mahalla sum and
the shabiya totals.

**The foreign exchange appendices name names.** Every accepted letter-of-credit
coverage request is published with the beneficiary firm and the dollar amount,
roughly 3,000 companies per release. That is firm-level access to hard currency
at the official rate, in a country where the gap between the official and
parallel rate is the central distributive question. No international dataset on
Libya contains it.

## Headline findings from Phase 1

The Central Bank of Libya publishes continuous monetary series from 2004 to the present and is the
only Libyan institution with a run long enough for time-series work. The Bureau of Statistics and
Census holds the 2006 census disaggregated to municipality, the last full enumeration and the
implicit baseline for most downstream Libyan data. The High National Elections Commission holds
results, voter registration and constituency data for every election since 2012 and is the largest
untapped source for Libyan political science.

Three constraints shape everything that follows. Almost nothing is machine-readable — of 40
institutions, one is harvestable by design and the rest publish PDF or client-side HTML, so
extraction rather than collection is where the work lies. Seven sites block datacenter IPs,
including three of the most valuable, which means a naive cloud-hosted scraper will silently
conclude that Libyan election data does not exist. And the 2011 and 2014 ruptures are visible in
the data itself, as gaps and discontinued series, so they need to be documented as properties of
the data rather than interpolated away.

One site, the Tax Authority (tax.gov.ly), is compromised and serving injected spam. Details in the
access notes.

## Roadmap

See [`docs/roadmap.md`](docs/roadmap.md).

Next: the geographic concordance mapping the census's 22 shabiyat and 667
mahallas onto the current municipality system, which is what everything
subnational will join on; BSC foreign trade 2005-2016; and the international
source inventory.

## Scope

The repository covers data *about Libya*, with priority on data *produced in Libya*. Phase 1
deliberately excludes World Bank, IMF, UN and other external producers so that the Libyan record
can be established on its own terms before external re-coding is layered on top.

## Contributing

Source additions should include a row in `sources/libyan_sources.csv` with the access status
actually observed, not the status claimed by the institution. Record a verification date. If a
source is unreachable, say why and from where — an IP block and a dead domain are different
findings and should not be recorded the same way.
