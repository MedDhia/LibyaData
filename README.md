# LibyaData

A harmonized, documented data repository on Libya for social science research.

Libyan data is not so much missing as scattered, undocumented, and published in formats that resist
analysis. The national statistical office, the central bank, the elections commission and the audit
bureau all publish real material — as PDFs, on sites that render client-side, behind firewalls that
block automated access, across an institutional landscape that has been split since 2014. The
purpose of this repository is to collect that material, document its provenance and its gaps, and
release it in tidy, analysis-ready form.

## Status

**Phase 1 — source identification.** Complete for Libyan-domiciled sources.

40 Libyan institutions inventoried and probed on 2026-09-09:

- [`sources/libyan_sources.csv`](sources/libyan_sources.csv) — machine-readable inventory, 18 fields
  per institution covering sector, data domains, geographic level, temporal coverage, formats,
  languages, update frequency and verified access status.
- [`sources/README.md`](sources/README.md) — narrative guide, ranked by research value, with the
  confirmed holdings of each major source and an assessment of coverage by research domain.
- [`sources/access_notes.md`](sources/access_notes.md) — what is blocked, what is broken, what is
  compromised, and how to reproduce the reachability check.

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

Next: extend the inventory to international and multilateral sources on Libya, then begin
extraction, starting with the CBL monetary series and the BSC census.

## Scope

The repository covers data *about Libya*, with priority on data *produced in Libya*. Phase 1
deliberately excludes World Bank, IMF, UN and other external producers so that the Libyan record
can be established on its own terms before external re-coding is layered on top.

## Contributing

Source additions should include a row in `sources/libyan_sources.csv` with the access status
actually observed, not the status claimed by the institution. Record a verification date. If a
source is unreachable, say why and from where — an IP block and a dead domain are different
findings and should not be recorded the same way.
