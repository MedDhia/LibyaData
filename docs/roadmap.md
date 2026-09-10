# Roadmap

## Phase 1 — Source identification (Libyan-domiciled) — done

40 institutions inventoried and probed 2026-09-09. Output in `sources/`.

## Phase 2 — Complete the source map

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

- **Geographic concordance.** Libyan administrative units have been reorganised repeatedly —
  muhafazat, then the 22 shabiyat the 2006 census uses, then the current municipality (baladiya)
  system, with boundary and name changes throughout. A crosswalk mapping every unit appearing in
  any source to a stable internal identifier, with validity dates, is a prerequisite for joining
  anything subnational, and nothing else in Phase 4 can proceed without it. The census extraction
  supplies one side of it already: 22 shabiyat and 667 mahallas with stable keys.
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
