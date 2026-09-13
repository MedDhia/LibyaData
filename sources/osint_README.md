# Open-source intelligence sources on Libya

Companion to [`libyan_sources.csv`](libyan_sources.csv), which inventories institutions inside
Libya. This one inventories the external, open-source layer: who else observes Libya, what they
publish, and whether a machine can read it.

32 producers, probed on 2026-09-12 from a datacenter address. Every `access_status` in
[`osint_sources.csv`](osint_sources.csv) is what the probe actually returned, not what the producer
claims. 20 answered openly, 9 need a registration key, 1 blocks this address, 1 has been
repurposed, and 1 is live but with no reachable API path.

The division of labour matters. Libyan institutions publish the record of the state: budgets,
census, elections, monetary accounts. The sources here publish the record of what happens to the
state and around it, and they are the only route to several things Libyan institutions do not
measure at all, or stopped measuring in 2011.

## Where the value is

**Conflict events.** ACLED is the reference dataset for Libya, geocoded to the point, 1997 onward,
with actor names that are the natural join to any armed-group roster. It no longer answers
unauthenticated reads: `api/acled/read` returns `{"message":"Access denied"}` and `/oauth/token`
answers 405 to GET, so the free key and its OAuth flow are now mandatory. UCDP moved the same way
and asks for an `x-ucdp-access-token` header. Airwars is neither, and is more careful than both on
civilian harm: incident-level records with explicit source chains and confidence grading, published
as structured pages rather than an API.

**Displacement, which is the subnational series Libya lacks.** IOM's Displacement Tracking Matrix
assesses IDPs, returnees and migrant stock at baladiya and mahalla level, quarterly, 2016 onward.
That is the same geography this repository has spent the last two phases harmonising, so it joins
to `concordance_mahalla.csv` directly and is the obvious next subnational dataset. Its own API is
not reachable: `dtm.iom.int/api` returns 403 and every `dtmapi.iom.int` path tried returns 404. Four
DTM datasets are mirrored on HDX, which is the way in. UNHCR's population API is open with no key
and returned 278,177 IDPs in Libya for 2020 on the first call.

**HDX as an aggregator, not a source.** 228 Libya datasets. The providers behind them are what
matter: World Bank 23, UNOSAT 22, Humanitarian OpenStreetMap Team 12, OCHA ROMENA 11, Insecurity
Insight 10, REACH 8, WorldPop 7. Formats are 63 XLSX, 54 SHP, 22 Geodatabase, 19 GeoTIFF, 19
Geopackage. Licences vary per dataset and several are share-alike or non-commercial, so anything
taken from here belongs under `data/external/` with its own notice, the way the nighttime lights
and OSM extracts already are.

**Imagery that has already been interpreted.** UNOSAT's 22 Libya products are analyst-verified
damage assessments: the 2023 Derna flood, and building-level damage from successive rounds of
fighting. Using them avoids having to do the geolocation yourself. NASA FIRMS gives daily VIIRS
thermal anomalies, which over Libyan oil infrastructure is a flaring and throughput proxy at higher
frequency than any production statistic, and needs only a free key.

**Sanctions and the elite.** The UN consolidated list is one 2.1 MB XML holding 28 individuals and
3 entities under the Libya (1970) committee, carrying reference numbers `LYi.001` upward and
`LYe.001` upward. OFAC's SDN file is open CSV, 5.7 MB, with `LIBYA2` and `LIBYA3` programme tags.
OpenSanctions has already resolved both into a merged graph: 293,095 sanctioned entities and
710,657 politically exposed persons, downloadable in bulk as a 178 MB CSV with no key, though the
search API needs one. For the officials dataset discussed earlier, that bulk file is the fastest
first pass, and Wikidata is the reconciliation target: 151 people holding a position applicable to
Libya, 135 of those statements dated, CC0.

**Connectivity as a political observable.** IODA and Cloudflare Radar both measure Libyan internet
reachability by country and network, and they disagree on some events, which is a reason to carry
both. OONI measures which sites are blocked on which Libyan networks, volunteer-collected, so thin
and irregular; absence there is absence of measurement, not absence of blocking.

**Movement.** OpenSky returns live ADS-B state vectors for a Libyan bounding box with no account at
all, six aircraft at probe time; historical tracks need a free login. ADS-B Exchange does not filter
military and state aircraft, which is the reason to want it, but its API is commercial. Global
Fishing Watch is the open route to tanker movement at Es Sider, Ras Lanuf, Zawiya and Brega and to
ship-to-ship transfers offshore, on a free token.

**Text corpora.** GDELT indexes global coverage with Libya filterable by `sourcecountry:LY` or by
language; its DOC API refuses more than one request every five seconds and says so in the response
body rather than returning 429, so a naive loop silently collects error text instead of data. Among
Libyan outlets, Libya Update exposes an open WordPress REST API with 6,160 posts, the same
enumeration pattern already used here for HNEC and parliament.ly, and Libya Herald serves RSS.
Libya Observer has no feed or sitemap at the standard paths. Alwasat returns 403 to this address,
the same pattern as the seven Libyan hosts in `access_notes.md`.

## What to be careful about

**One source has been repurposed.** `libyancrimeswatch.org` no longer serves the human rights
organisation's site. It returns a FingerprintJS script that redirects with a tracking UUID. Anything
collected from that host after this date should be treated as untrusted, and their documentation
sourced from mirrors instead. This is the second Libya-relevant domain in this repository found in
that state, after `tax.gov.ly`.

**Editorial line is a variable, not noise.** Libya Observer and Libya Herald do not cover the same
events the same way, and neither matches Alwasat. A news corpus built from whichever outlet is
easiest to scrape inherits its politics. Any corpus here needs the outlet recorded as a column and
at least one Tripoli-aligned and one eastern-aligned source in it, for the same reason the gazette
question needs a `publishing_authority` column.

**Coverage is not observation.** ACLED and UCDP code from reporting, so their density tracks where
journalists and monitors are, which in Libya means the coast. OONI and OpenSky depend on volunteers
and receivers, which means the same. Sparse interior counts are an artefact of the instrument.

**Licences do not travel.** ODbL on OSM is share-alike, GADM is non-commercial, several HDX datasets
carry their own restrictions, and OpenSanctions states no licence in its API index. This repository
already isolates such material under `data/external/` with a NOTICE beside it, and anything taken
from this inventory should go the same way.

## Reproducing the check

Each row records the endpoint probed and the HTTP result in `verified_2026_09_12`. The probes were
plain GETs with a browser user agent and a 20-second timeout. Re-running them from an ordinary
connection rather than a datacenter address should change at least the Alwasat row, and possibly
others: `parliament.ly` answered this time despite being recorded as WAF-blocked in
`access_notes.md`.
