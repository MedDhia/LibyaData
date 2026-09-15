# Italy as a source on Libya, 1911 to 1943

Where the Italian colonial statistics on Libya are, which of them can be downloaded, and which
Italian catalogue cannot be searched from here. Built by
`scripts/download_istat_colonial.py`; the manifest is in `data/raw/istat/manifest.json`.

## The short answer

The Italian colonial statistics on Libya are not in a library catalogue that has to be negotiated.
They are in **ISTAT's own digital library**, served as a plain Apache directory index, every file a
direct PDF download with a text layer. Three things are there, and all three are downloadable:

| What | Where | Size |
|---|---|---|
| **Censimento della popolazione delle colonie italiane al 1° dicembre 1921**, with a section on the enumerations before it | `Censimenti popolazione/censpop1921/` | 186 pages, 9.2 MB |
| VII censimento generale della popolazione 1931, **Volume V, Colonie e possedimenti** | `Censimenti popolazione/censpop1931/` | 215 pages, 17.3 MB |
| VIII censimento generale della popolazione 1936, **Volume V, Libia, Isole italiane dell'Egeo, Tientsin** | `Censimenti popolazione/censpop1936/IST0005817vol5_.../` | 252 pages, 18.0 MB |
| **Annuario statistico italiano**, the complete run 1911 to 1943, 26 volumes, with a Libyan chapter inside each | `Annuario Statistico Italiano/` | 746 MB in all |

Three counts of the Libyan population, in 1921, 1931 and 1936, with an annual series around them.

This matters because of where the rest of the record stands. This repository's census data begins in
2006. The BnF holds the Libyan censuses of 1954 and 1964 and a statistical abstract for 1958-1974,
**none of it digitised** (`sources/bnf_README.md`). The Italian material is thirty years older than
any of that and it is already online.

## The three censuses

**1921.** `Censimento della popolazione delle colonie italiane al 1° dicembre 1921`, Serie VI volume
XX, printed in Rome in 1930-31, nine years after the count. It opens with `RILEVAZIONI PRECEDENTI:
Tripolitania, Cirenaica, Eritrea, Somalia`, which is a summary of what had been counted in the
colonies before, so the volume reaches back past its own date. Libya is still two colonies here,
Tripolitania and Cyrenaica, and is not yet called Libia.

**What 1921 counted is not what 1931 and 1936 counted.** This is the VI general census of the
*Italian* population, extended to the colonies: 18,566 people present in Tripolitania and 8,607 in
Cirenaica, against 543,672 and 160,451 ten years later. The difference is the indigenous population,
which 1931 enumerated and 1921 did not, and the ground Italy had taken in between. Putting the three
counts in one series would measure the growth of the Italian census, not the growth of Libya. What
1921 gives instead is a map of where the colonial state sat ten years into the occupation: Tripoli
is 16,010 of Tripolitania's 18,566, Bengasi 6,079 of Cirenaica's 8,607, and four of the
twenty-three centres held fewer than ten people each.

**1931, Volume V.** The colonies counted on the same day as the Kingdom, 21 April 1931, under rules
agreed between the Istituto Centrale di Statistica and the Ministero delle Colonie. The volume
separates `popolazione regnicola` (Italians from the Kingdom), `straniera` (foreigners) and
`indigena` (the indigenous population), the last enumerated on its own form and given until 31
December 1931 to complete. Tripolitania and Cyrenaica are throughout.

**1936, Volume V.** A volume for Libya alone, published in Rome in 1939. Its tables run by
`sottozone militari`, and the Libyan population is tabulated by sex and age, religion, "razza",
language, type of dwelling (sedentary, semi-nomadic, nomadic) and category of economic activity.

Two appendices make it more than a census report:

- **Appendix I, `Atti relativi al censimento della Libia`**: the instructions the Istituto issued,
  which is the codebook for everything in the volume.
- **Appendix II, `ELENCO ALFABETICO DELLE LOCALITÀ DELLA LIBIA`**: every locality named in table XX,
  with the political and administrative circumscription it belonged to on 21 April 1936.

That second appendix is a gazetteer of Libyan places with their administrative parent and, through
table XX, their population. It is the same object as this repository's mahalla concordance, seventy
years earlier, and matching the two would give Libyan settlement geography a pre-war anchor it does
not have.

## The yearbook run, which is the larger find

The `Annuario statistico italiano` is here complete from 1911, the year of the invasion, to 1943,
the year the colony was lost: 26 volumes, three of them covering pairs or runs of years, 746 MB in
all. The Libyan material is a chapter inside each volume, so no filename search finds it, which is
why the years are listed by name in the script.

In the volume for 1938, chapter XIX, `Africa Italiana - Possedimenti`, section B runs from page 325
to page 335 and tabulates, for Libya:

- the 1936 census by province, and the movement of the national, foreign and assimilated population
- the census of agricultural holdings, productive and unproductive area by province, and the
  population living on metropolitan farms
- shipping in the ports of western and eastern Libya, by port and flag, vessels, net tonnage and
  cargo landed and embarked
- foreign trade: imports and exports by principal country of origin and destination and by the
  sections of the statistical nomenclature, three years to a table
- **quantities and prices of produce sold in the markets of Tripoli, Misurata, Bengasi and Derna**:
  wheat, barley, potatoes, onions, dates, oil, and mutton, veal, camel, beef, lamb and goat meat,
  city by city
- migration through the Commissariato per le migrazioni
- agricultural credit operations
- schools and institutes, metropolitan-type and other

Thirty-odd volumes of that is an annual colonial panel: population, agriculture, trade, shipping,
migration, credit and education by province, and market prices by city, from 1911 to 1943.
`Movimento commerciale del Regno d'Italia` sits in the same library as a separate annual series,
1881 to 1938, and carries the colonies from 1912.

## What could not be checked from here

**OPAC SBN, the Italian union catalogue, cannot be searched from this environment.** The site
answers HTTP 200 and renders its results in JavaScript, so the HTML of a search page carries no
records. Its documented machine interface is Z39.50 on ports 2100 and 3950, and this session has no
egress but HTTPS through a proxy. The obvious fallback, a headless browser, does not work either:
the bundled Chromium does not trust the proxy's certificate authority and fails every HTTPS
navigation, `example.com` included, with no `certutil` available to add the CA. Internet Culturale
renders client-side in the same way, and HathiTrust returns 403 to scripted clients. The Internet
Archive is reachable and holds almost nothing of this: a search for the colonial statistical series
returns zoological expedition reports.

So this is ISTAT's holdings, checked, and not the holdings of the Biblioteca Nazionale Centrale in
Rome or Florence, which are unchecked. What those add is likely to be the Libyan colonial
government's own publications rather than Rome's: the `Bollettino ufficiale del Governo della
Tripolitania` and its Cyrenaican counterpart, and the `Bollettino del Reale Ufficio per i servizi
agrari della Tripolitania`, which the BnF catalogue lists for 1932-1936 and does not have digitised.
Searching OPAC SBN for those is a job for an ordinary connection.

## What to do next, in order of value

1. ~~Extract Appendix II of the 1936 census, the locality list, and match it against
   `data/processed/concordance_mahalla.csv`.~~ **Done**, by
   `scripts/extract_istat_1936_localities.py`: 1,090 localities, 870 placed in a modern shabiya
   through their circumscription, and 48 joined to a mahalla of the 2006 census on a consonant
   skeleton within the same province. Table XX of the same volume holds the population of each, and
   extracting that is the obvious next step.
2. Pull the Libya chapter out of each yearbook volume from 1911 to 1943 and build the colonial
   panel. The chapter is a fixed structure across volumes, which is what makes it tractable.
3. ~~Extract table XX of the 1936 volume, the population of each locality.~~ **Done**, by
   `scripts/extract_istat_1936_population.py`.
4. ~~Read the 1921 census of the colonies.~~ **Done**, by
   `scripts/extract_istat_1921_libya.py`: the 23 inhabited centres of Tripolitania and Cirenaica
   with families, present and resident population, every column exactly as the volume prints it.
   They are read from the summary that opens each chapter rather than from table I, whose nine
   columns are the better table but whose Cirenaica page the scan damaged past repair. **Re-OCR of
   PDF pages 31 and 73 would recover six more columns and the quarters of Tripoli and Bengasi**,
   and is the cheapest unclaimed gain in this volume.
5. The 1931 volume is read as far as it can be: `scripts/extract_istat_1931_libya.py` publishes its
   table I, area and the four populations by circumscription for both colonies, with Cyrenaica
   exactly as printed. Its table II, the district detail, is not machine-readable from this scan and
   is recorded as such. Re-OCR of those two pages would recover it.
6. Search OPAC SBN from an unblocked connection for the colonial government's own bulletins, which
   are the administrative record the statistics were drawn from.
