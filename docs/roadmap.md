# Roadmap

## Phase 1 — Source identification (Libyan-domiciled) — done

40 institutions inventoried and probed 2026-09-09. Output in `sources/`.

## Phase 2 — Complete the source map

**2.0 Open-source intelligence producers — done.** 32 producers inventoried and probed 2026-09-12.
Output in `sources/osint_sources.csv` and `sources/osint_README.md`: conflict events, displacement,
imagery analysis, sanctions and PEP records, network measurement, transport tracking, and news
corpora. 20 answer openly, 9 need a free registration key, 1 blocks datacenter addresses, and
`libyancrimeswatch.org` has been repurposed into a fingerprinting redirect and is no longer the
organisation's site. The two to take first are IOM's Displacement Tracking Matrix, which assesses
IDPs and returnees at the same baladiya and mahalla level this repository has already harmonised,
and the OpenSanctions bulk files, which carry the UN and OFAC Libya designations already resolved.

**2.1 International and multilateral producers.** World Bank WDI, IMF (Article IV and IFS), UN
Statistics, UNDP, UNHCR, IOM Displacement Tracking Matrix, OCHA HDX, WHO, FAO, OPEC, EIA, ACLED,
UCDP, V-Dem, Afrobarometer and Arab Barometer where Libya is covered. Each needs the same fields as
the Libyan inventory plus a flag for whether its Libya figures are original collection or a
restatement of a Libyan source — a great deal of "international" Libya data is BSC or CBL output
passed through, and treating it as independent corroboration would be an error.

**2.2 Eastern and parallel institutions.** The 2014 split produced competing authorities issuing
competing figures. The eastern central bank branch, the eastern government and the eastern NOC claim
did not resolve to reachable domains in the Phase 1 sweep and need a dedicated search. Where two
authorities publish a figure for the same quantity, the repository stores both, tagged by issuing
authority. It does not adjudicate.

**2.3 Decide on social media as a source type.** Several real institutions — the General Electricity
Company of Libya, the Man-Made River Authority, the Ministry of Local Government, the High Council
of State, the Central Committee for Municipal Council Elections — operate with no working website
and publish through Facebook. Excluding them loses genuine data; including them raises archiving,
citation and stability problems. This needs an explicit decision rather than a default.

## Phase 3 — Extraction

Done, with a validation suite in `scripts/validate.py`:

1. **CBL monetary series, 2004–2026.** Money supply, monetary base, required reserves and both
   counterpart decompositions, monthly with no gaps and every accounting identity holding exactly.
   Plus annual capital adequacy.
2. **CBL uses of foreign exchange.** By bank, by purpose, and the full appendix set down to named
   beneficiary firms. Reconciles to within $5 of the CBL's own published totals.
3. **BSC consumer price index**, 2015–2026 by COICOP division, separated by base year.
4. **BSC publication catalogue**, 248 documents enumerated through the sitemaps.
5. **BSC 2006 census by mahalla**, 667 localities across all 22 shabiyat, plus shabiya area and
   density. Reconciles exactly to the published national population and area. This is the
   subnational baseline everything else joins to.
6. **BSC 2006 census, all 74 tables**, 1,014,208 figures across eleven sections and 22 volumes,
   read structurally rather than by hard-coded schema.

Remaining, in order of value over effort:

7. **BSC foreign trade, 2005–2016**, reconciled against the CBL foreign trade reports. Also the
   Ministry of Economy daily commodity rates, as an independent price series covering the CPI gap
   years.
8. **CBL assets and liabilities, and the consolidated commercial bank balance sheet.** Both are
   bilingual right-to-left layouts with figures in reverse column order; the column mapping needs
   validating against known totals before the data can be trusted.
9. **HNEC electoral results, 2012–2026**, contingent on solving the access problem.
10. **Audit Bureau annual reports** — spending by ministry and state company. Manual retrieval,
   heavy extraction, high payoff for political economy work.
11. **LANA newswire corpus** via sequential ID enumeration, as a text corpus rather than a table.

## Phase 4 — Harmonization

The part that makes this a repository rather than a folder of scraped PDFs.

- **Geographic concordance.** Partly done. `concordance_shabiya.csv` maps the 22 first-level units
  across all three naming systems in play — the census, GADM 4.1 and COD-AB — each mapping checked
  by ranking units on area rather than name similarity. `concordance_mahalla.csv` gives all 667
  mahallas a stable key, a normalised Arabic join key and their parent unit in every system, and
  147 of them carry an OpenStreetMap coordinate.

  The mahalla-to-baladiya link is now largely in place, from HNEC's 2021 polling-centre register,
  which lists every centre with both its locality and its municipality, and from the 2024 and 2025
  municipal documents that restate the municipality of the same centres by code. 402 of the 667
  mahallas are mapped, 5 are ambiguous, 260 remain, and `baladiya_source` says which of the five
  routes established each link. Coverage is highest where settlement names are stable (Sabha and
  Kufra 100%, Nuqat al Khams 83%) and lowest in the big cities (Benghazi 38%) and the south
  (Murzuq 33%), whose mahallat were most often renamed or re-cut.

  HNEC's media library is exhausted for the remainder: its 3,491 PDFs were enumerated and the only
  other polling-centre vintages, from July and November 2021, are page scans with no text layer, as
  are Decision 50 of 2023 on the municipal electoral districts and the 2025 list of targeted
  municipalities. The 2,404 voter lists name individuals and are deliberately excluded. Closing the
  gap needs the annex to Decree 180 of 2013 listing each municipality's constituent localities, a
  boundary layer below the shabiya, or optical character recognition of the scanned registers.
- **Transliteration standard.** Arabic place and institution names arrive in several romanisations
  across sources. Pick one, apply it consistently, and keep the Arabic original in a parallel column.
- **Temporal alignment.** Fiscal, Gregorian and Hijri years all appear. Store the original and a
  normalised Gregorian equivalent.
- **Currency and units.** LYD figures span multiple exchange-rate regimes including the 2020
  devaluation. Store nominal values as published; never silently convert.
- **Provenance.** Every observation carries its source institution, document, page, retrieval date
  and a checksum of the source file. A figure whose provenance cannot be stated does not enter the
  repository.
- **Contested values.** Where authorities disagree, store all versions with the issuing authority
  attached.

## Phase 5 — Release

Tidy CSVs, one file per series, with a codebook per file, versioned releases, and a citation file.
Given the user base, R and Stata read-in examples should ship alongside. Following the user's
convention, R examples use stargazer for table output.

## Principles

- Record what was observed, with a date. An IP block, a dead domain and an institution that never
  published are three different findings.
- Store gaps as gaps. Libyan series break in 2011 and thin after 2014; that discontinuity is
  information about the Libyan state and should survive into the released data rather than being
  smoothed over.
- Never adjudicate between competing authorities. Store both, tag the issuer, let the analyst decide.
- Mirror everything on ingest. Libyan government sites go down, get reorganised, and in at least one
  documented case get compromised.
