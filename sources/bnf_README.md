# The Bibliothèque nationale de France as a source on Libya

What the BnF holds on Libya, what of it carries data, and what can be read from here.
Built by `scripts/download_bnf_catalogue.py` and coded by
`scripts/extract_bnf_libya_sources.py`; the tables are in `data/processed/bnf/`.

## Why look there

Libya's own statistical record starts late and breaks in 2011. The Bureau of Statistics has
published little since, and the last census it completed was in 2006, which is where this
repository's census data begins. Everything before independence in 1951 was collected and published
by somebody else: the Ottoman administration to 1911, the Italian colonial state to 1943, then a
British administration in Tripolitania and Cyrenaica and a French one in Fezzan. The BnF holds the
French half of that record and a long run of French consular and geographical reporting on the
Regency of Tripoli before it.

## What is actually there

4,396 catalogue records name Libya or one of its provinces. 873 are digitised in Gallica. Neither
number means what it appears to.

| Class | Records | Digitised |
|---|---|---|
| Printed books | 2,201 | 103 |
| Coins and medals | 749 | 0 |
| Maps | 604 | 295 |
| Photographs | 525 | 427 |
| Serials | 131 | 8 |
| Manuscripts and archives | 40 | 31 |
| **Data-bearing records** | **43** | **5** |

The largest search term in the catalogue is "Cyrénaïque", and most of what it returns is Greek
coinage in the Cabinet des Médailles: drachms struck at Barka and Teuchira, catalogued one by one
and photographed. The 1900-1919 band holds 338 digitised records because the Italo-Turkish war of
1911 was photographed heavily. A count of Libya records is not a count of Libya data.

## The data-bearing holdings

43 records, listed in `data/processed/bnf/bnf_libya_data.csv`. Five things in them matter.

**The two censuses before the ones we have.** `General population census 1954: report and tables`
(Ministry of National Economy) and `The General population census 1964` (Census and Statistical
Department), with `Population census paper` and `The Labour force of Libya` from the same
department. Libya's first two censuses, held at the BnF, **not digitised**. This repository's census
data starts in 2006; these are the missing end of the series.

**A statistical abstract running 1958 to 1974**, a reproduction of the United Kingdom of Libya's own
series, covering the monarchy and the first five years after it. Also not digitised. With the two
censuses it is the backbone of any long Libyan series, and all of it is on a shelf in Paris.

**The Italian colonial statistics.** `Statistica del movimento commerciale marittimo dell'Eritrea,
della Somalia italiana, della Tripolitania e della Cirenaica` (1923), the `Bollettino del Reale
Ufficio per i servizi agrari della Tripolitania` (1932-1936), and the `Relazione della missione
demografica` of 1933. Maritime trade, agriculture and population, under the categories the colonial
state used. None digitised.

**Two French consular series that are digitised in full**, and are the reason this search was worth
running:

- `Bulletin consulaire français: recueil des rapports commerciaux adressés au Ministère des affaires
  étrangères` (1877-1914) — <https://gallica.bnf.fr/ark:/12148/cb34447967w/date>
- `Rapports commerciaux des agents diplomatiques et consulaires de France` (1892-1914) —
  <https://gallica.bnf.fr/ark:/12148/cb34447966j/date>

These are annual commercial reports filed by French consuls, and the French consulate in Tripoli was
one of the posts filing them. **That the Tripoli reports are in these volumes has not been verified
from here**, because Gallica refuses this address; the catalogue proves the series exists and is
digitised, not what is inside a given year. The check to run from an ordinary connection is the
table of contents of any volume, looking for Tripoli or Tripolitaine. `Annales du commerce
extérieur. Tripolitaine. Législation commerciale` (1912) is a separate record and proves the French
trade annals did carry a Tripolitanian volume, though that one is not digitised.

**A manuscript gazetteer of the Regency of Tripoli.** Jacques-Denis Delaporte's `Nomenclature des
villes et villages de la régence de Tripoli`, digitised —
<https://gallica.bnf.fr/ark:/12148/btv1b108700649>. A settlement list for Ottoman Libya, which is
the same kind of object as this repository's mahalla concordance and a century older than anything
in it. Alongside it sit consular dispatches on the commerce of Tripoli and Benghazi from the 1820s,
also digitised, and `Statistique sur le commerce de Benghazi (1828)`, a modern edition that is not.

## The maps, which are the largest usable stratum

295 digitised maps: 213 from before 1911 and 15 from the Italian period, the rest undated. The
Italian survey material is the geospatial part — `Triangolazione della Tripolitania in Cirenaica`,
`Carta dimostrativa della Cirenaica` from the Ministero delle Colonie, three sets of Libyan city
plans, all 1914 — with `Ben-Ghazi & Libyan desert` from the Survey Department of Egypt in 1915. They
are georeferenceable and they show settlement before the mass displacements of the 1920s and 1930s,
which is exactly the period no boundary layer in this repository reaches.

## What can be read from here, and what cannot

**gallica.bnf.fr refuses this repository's addresses** — `403 Access Interdit` on every path,
including the SRU service and the IIIF manifests. The BnF general catalogue at
`catalogue.bnf.fr/api/SRU` answers normally and carries the Gallica ARK of every digitised record,
so the inventory is complete and the documents are not. See `sources/access_notes.md`.

That division decides the next step. The inventory says which ARK to fetch; fetching is a job for an
ordinary connection.

## What to do next, in order of value

1. Fetch the two consular series from Gallica and check whether the Tripoli reports are there. If
   they are, forty annual observations of Libyan trade, shipping and prices under Ottoman rule
   become available in one pass.
2. Order or consult the 1954 and 1964 censuses and the 1958-1974 statistical abstract. They are not
   digitised anywhere, and they are what a long Libyan population or economic series needs.
3. Georeference the 1914 Italian survey maps and the 1915 Survey of Egypt sheet against the
   concordance, which would give this repository its first pre-war settlement geography.
4. Repeat the catalogue search at other national libraries. The Italian record is the one this
   search cannot see: the Biblioteca Nazionale Centrale and the Istituto Centrale per il Catalogo
   Unico hold the colonial statistical series, and the BnF has only what reached Paris.
