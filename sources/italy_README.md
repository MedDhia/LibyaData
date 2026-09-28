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
2. ~~Pull the Libya chapter out of each yearbook volume from 1911 to 1943.~~ **Half done**, by
   `scripts/extract_istat_annuario_index.py`, which finds the colonial chapter in each of the 26
   volumes and lists every table in it that concerns Libya: 292 tables, with the file and page of
   each. A second pass repaired three faults. The 1922 to 1930 volumes open the chapter with a
   contents page that the first pass read as tables. The running head that marks the chapter's
   pages is damaged or reduced to `Colonie` in several scans, which cut the 1938 chapter off before
   its market prices, credit and school tables. And the Aegean section of 1937 and 1938 was filed
   under Libya. The chapter is now followed by its title matched loosely, or by its numeral, and
   the rows of 1915, 1922, 1930, 1937 and 1938 were checked against the page images. The chapter
   is **not** a fixed structure across volumes, which is why this is an index and
   not yet a panel. It is called `Possessi e Protettorati italiani`, then `Colonie e Possedimenti`,
   then just `Colonie`, then `Impero - Colonie - Possedimenti`, then `Africa Italiana`; Libya is one
   colony, then two, then one again, then four provinces and a desert.

   The series that came out of it is **seaborne trade, 1922 to 1936**, in
   `data/processed/istat/libya_annuario_trade.csv`: imports and exports of Tripolitania and
   Cirenaica in thousands of lire, 30 colony-years. It was **transcribed by hand**. A reader was
   written for it first and thrown away, because the scan truncates bold total lines without making
   them look wrong, and no tolerance loose enough to read the damage is tight enough to be trusted.
   So the seventeen pages the index located were rendered as images and read by eye, and checked
   against the arithmetic the source supplies itself: each table lists the trade by country, and
   those columns sum to the printed total. Every figure was accepted only where the countries added
   up to it.

   That check is what makes the file worth having. It corrected the reader's 211,288 to 215,266 and
   its 141,884 to 141,634; it caught two misprints in the volumes themselves; and it identified five
   places where a later volume revises an earlier one, which are published as revisions rather than
   averaged away. 23 of the 29 colony-years that carry figures are printed in two or more volumes and agree.

   **Shipping, 1921 to 1937**, is the second series, in
   `data/processed/istat/libya_annuario_shipping.csv`, published by
   `scripts/extract_istat_annuario_shipping.py` from 25 pages in twelve volumes: vessels, net
   tonnage, cargo and passengers by port, flag and propulsion. Steam and sail add to the whole and
   the ports to the colony in 1,586 sums, and the four places where volumes disagree are each a
   revision the later volume's footnote announces. Ships arriving at Tripoli carried 285,842 net
   tons in 1923 and 1,417,043 in 1937.

   **Population** is the third, in `data/processed/istat/libya_annuario_population.csv`, from
   `scripts/extract_istat_annuario_population.py`. Its new part is the 1931 census by
   commissariato with religion, race and dwelling type, which the 1936 yearbook prints and the
   1931 census tables transcribed here do not: 26% of Tripolitania's Libyans were counted
   seminomadic or nomadic. Its reprints of the 1936 census agree with the census volume in all 811
   figures. The provisional 1936 count of 772,999 Libyans, printed in 1937 and 1938, is kept apart
   from the census's 750,851.

   **Market prices** are the fourth, in `data/processed/istat/libya_annuario_market_prices.csv`:
   quantities sold and lowest and highest prices of 23 products in Tripoli, Misurata, Bengasi and
   Derna in 1937, and average prices in five Sahara markets in 1938 and 1939. No other volume in
   the run prints market prices for Libya. **Railway traffic**, 1923-24 to 1935-36, is the fifth.
   **Schools**, 1934-35 to 1939-40, the sixth, add up across type, region, nationality and
   religion. Credit and the smaller series come next.

5. ~~The 1931 volume's table II, the district detail, is not machine-readable from this scan.~~
   **Done**, by transcription rather than by re-OCR. `scripts/extract_istat_1931_districts.py`
   publishes 106 rows two levels below the circumscription, with the sex breakdown table I does not
   carry. The two pages were rendered as images and read by eye, and the transcription is bound by
   four arithmetic checks the hierarchy supplies: the three populations sum to the total on every
   row and for women alone, no female count exceeds its total, every parent equals its children, and
   the circumscriptions sum to the colony. Those checks caught the only two errors in the first
   reading. The transcription also repairs five cells the scan destroyed in table I, so every
   population column of `libya_1931_circoscrizioni.csv` now reconciles exactly.

   **Table III is now read too**, by `scripts/extract_istat_1931_residents.py`: 51 rows on the
   Italian and foreign population alone, distinguishing who was present on census night from who
   lived there, with the temporarily absent and the whole of it by sex. It passes six checks, the
   last of which ties it to table II across two separately transcribed pages: the population
   present in table III is table II's Italians plus its foreigners, and 102 figures agree.

   The Libyan tables of the 1931 volume are now all read.

6. ~~The 1936 volume's section I.~~ **Done**, by
   `scripts/extract_istat_1936_circumscriptions.py`: tables I, II and III transcribed by eye, giving
   the administrative hierarchy of 1936 with the population present and resident, by nationality and
   by sex, and the 27 municipalities created by decree in 1935. All 432 figures of the municipality
   table equal the circumscriptions the volume's own footnotes say they are made of.

   **Table IV is now read too**, by `scripts/extract_istat_1936_residents.py`: the settler
   population present, temporarily absent and resident, by character of dimora and by where the
   absent were. Its finding is that 52,421 of the 115,637 Italians and foreigners counted in Libya
   in April 1936, 45% of them, had no habitual dwelling there, rising to 94% in the Circondario di
   Tòbruch and 85% in Derna. 276 of its figures cross-check against table II.

   **Tables XXI and XXII are now read too**, by `scripts/extract_istat_1936_libyans.py`: the
   Libyan population present and resident, 229 rows each, by way of life (stabile, seminomade,
   nomade), religion and Muslim rite, race in the census's own categories, language, and for table
   XXI age and sex, for table XXII family heads. They go a level below table II, naming the thirteen
   mudirie of the Fezzan. 276 of their figures cross-check against table II's `libica` columns.

   Three things come out of them. **110,830 of the 732,973 Libyans present, 15%, were counted
   seminomadic or nomadic**, from 99% in the Distretto di el-Azizìa down to nothing in the
   Circondario di Tripoli. **The Circondario di Nàlut held 8,457 of Libya's 29,541 Ibadis and 10,231
   of its 68,351 Berbers**, which locates the Ibadi Berber west in a single circumscription. And the
   present and resident tables together expose the Egyptian frontier: 8,359 Copts present, 4,028 of
   them at Porto Bardìa, and 73 people of `altre religioni` resident in the whole colony. The
   category `libica` was wide enough to hold an Egyptian labourer at Bardia.

   **Tables XXIII, XXIV and XXVI to XXIX are read too**, by
   `scripts/extract_istat_1936_libyan_families.py`: Libyan families by the activity and religion of
   the head and by size, Muslim marriage by the age of both spouses, polygamous husbands by number of
   wives, and the Libyans living in institutions. 142,993 monogamous heads and 5,507 polygamous
   husbands, 3.7%; the two polygamy tables agree in every cell, including the wives implied by the
   number each man had.

   **Table XXX is read too**, by `scripts/extract_istat_1936_libyan_age.py`: the Libyan
   population by age, sex, civil status and religion, per province. 38% of Libyan women aged 15 to
   19 were married, 2% of men; 35,621 widows against 8,556 widowers.

   **Tables XXXI and XXXII are read too**, by `scripts/extract_istat_1936_libyan_activity.py`:
   the Libyan population by category of economic activity, by sex and religion, and by
   circumscription and dimora. All 229 lines of XXXII carry table XXII's residents.

   **Tables XXXIII and XXXIV are read too**, by `scripts/extract_istat_1936_libyan_professions.py`:
   91 professions by province and sex, and by age. They carry the one misprint in the Libyan
   tables, 363 for 263 meat sellers in Bengasi, kept in the raw file and corrected with a note.

   **Table XXV is read too**, by `scripts/extract_istat_1936_libyan_children.py`: families by the
   number of co-resident children under 6, 15, 21 and of any age. With it every Libyan table of the
   volume except XX is transcribed and cross-checked, and XX keeps its automated extraction.

   **Tables V to XII are read too**, by `scripts/extract_istat_1936_settlers.py`: settler
   families by the social condition of the head, by size and by children; the convivenze; the
   population present and resident by single year of age; and foreigners by country. The present
   table counts 30,430 men aged 20 to 24 against 2,946 women.

   **Tables XIII to XIX are read too**, by `scripts/extract_istat_1936_settler_professions.py`:
   the settler population by category of activity, class, position and individual profession,
   with their families and ages. 7,943 of the 26,586 settlers at work were in public
   administration, 4,173 of them in the armed forces. Table XIX carries three misprints, kept in
   the raw file and corrected with a note where two independent sums agree. With these, every
   table of the volume's Libyan part is transcribed and cross-checked, and XX keeps its automated
   extraction.

6. Search OPAC SBN from an unblocked connection for the colonial government's own bulletins, which
   are the administrative record the statistics were drawn from.
