# Access and Retrieval Notes

Observed 2026-09-09 from a cloud host. Recorded so that later collection runs do not misread an
access failure as an absence of data.

## Sites that block datacenter IP ranges

Seven sources returned a block rather than content. In every case the material is public and loads
in an ordinary browser; the obstacle is a web application firewall, not a restriction on the data.

| Source | Domain | Symptom |
|---|---|---|
| High National Elections Commission | hnec.ly | Sucuri WAF, HTTP 403, block ID `BLACK02` ("Your IP address is listed in our blacklist") |
| Ministry of Health | health.gov.ly | Sucuri WAF, HTTP 403, block ID `BLACK02` |
| Social Security Fund | ssf.gov.ly | Sucuri WAF, HTTP 403 |
| Customs Authority | customs.gov.ly | HTTP 403 |
| Mellitah Oil and Gas | mellitahog.ly | HTTP 403 |
| Alwasat | alwasat.ly | HTTP 403 |
| Libyan Investment Authority (alt. domain) | libyaninvestment.com | Cloudflare JavaScript interstitial |

Changing the user agent does not help — the block is on the IP, and Sucuri returns the same
`BLACK02` response to a full browser UA string. Practical options, in order of preference:

1. Retrieve from a residential connection and deposit files into the repository manually.
2. Use archived snapshots where they exist.
3. Request an allowlist entry from the site operator, which is realistic for a named research
   project and worth attempting for HNEC specifically.

Do not work around this by disabling TLS verification or by rotating through proxies to evade the
block; document the gap instead.

## Foreign libraries that block the same way

Observed 2026-09-15.

| Source | Domain | Symptom | Workaround |
|---|---|---|---|
| Gallica, Bibliothèque nationale de France | gallica.bnf.fr | `403 Access Interdit` on every path, the SRU service and the IIIF manifests included; a browser user agent turns the refusal into a hang | Read the BnF **Catalogue général** instead, at `catalogue.bnf.fr/api/SRU`, which answers normally and carries the Gallica ARK of every digitised record in UNIMARC `856$u`. Fetch the documents themselves from an ordinary connection. |
| Bibliothèque numérique, Ministère de l'Europe et des Affaires étrangères | bibliotheque-numerique.diplomatie.gouv.fr | Incomplete TLS chain: `unable to get local issuer certificate`, with or without the agent proxy's CA bundle. A fetch through the harness returns `503` | None from here. The site mirrors Gallica ARKs for diplomatic material, so it is worth retrying from an ordinary connection when Gallica itself is unreachable. |

The catalogue route is what `scripts/download_bnf_catalogue.py` uses, and it is enough to build an
inventory: 4,396 records, 873 of them digitised. What it cannot do is read the documents, so the
contents of a series are recorded as unverified rather than assumed.

### The Italian catalogues, which are harder

| Source | Domain | Symptom | Workaround |
|---|---|---|---|
| OPAC SBN, the Italian union catalogue | opac.sbn.it | The site answers HTTP 200 but renders its results in JavaScript; the HTML of a search page carries no records. Its documented machine route is Z39.50 on ports 2100 and 3950, and this session has no egress but HTTPS through the proxy, so both are unreachable | None from here. A headless browser is the obvious answer and does not work either, see below |
| Internet Culturale | internetculturale.it | Same: HTTP 200, results rendered client-side, no OAI-PMH endpoint at the documented paths | None from here |
| HathiTrust | catalog.hathitrust.org, babel.hathitrust.org | HTTP 403 to scripted clients | None from here |
| ISTAT digital library | ebiblio.istat.it | **Works.** The library is a plain Apache directory index and every file is a direct PDF download | This is the route `scripts/download_istat_colonial.py` takes |

**Chromium cannot be used as a fallback in this environment.** The bundled browser does not trust
the agent proxy's certificate authority: every HTTPS navigation fails with
`ERR_CERT_AUTHORITY_INVALID`, `example.com` included, and `certutil` is not installed to add the CA
to the NSS store. Do not work around this by launching the browser with certificate errors ignored.
A JavaScript-rendered catalogue is therefore out of reach here, and OPAC SBN has to be searched from
an ordinary machine.

## Sites that return HTTP 200 but no usable body

| Source | Domain | Symptom | Workaround |
|---|---|---|---|
| Libyan Audit Bureau | audit.gov.ly | HTTP 200, empty response body to scripted clients | Manual retrieval |
| Bureau of Statistics and Census | bsc.ly | Publication listings (`/our-versions/`, `/blog/`) render client-side and expose no document links | Enumerate `https://bsc.ly/wp-sitemap.xml`, which indexes the `economic_statistics`, `demog_statist`, `vital-administrative`, `social_statistics` and `m-chart` post types |
| General Authority for Communications and Informatics | cim.gov.ly | JavaScript application, no server-side HTML | Headless browser |

## Compromised host

**tax.gov.ly** serves injected SEO spam on its homepage — outbound links to gambling sites
(`accslot88`, `OLXBET288`, `VIPBET76`, `Toto Slot`) and a large block of unrelated commercial
domains. The site is compromised.

Consequences for this project: do not ingest documents from this host without independent
corroboration, do not follow outbound links from it, and record the compromise date alongside
anything already collected from it. Libyan tax law texts should be sourced from the Official
Gazette on parliament.ly instead.

## Domain repurposed

**libyancrimeswatch.org** no longer serves Libyan Crimes Watch. As of 2026-09-12 it returns a
FingerprintJS script that redirects the visitor with a tracking UUID (`?tr_uuid=...&fp=`). The
organisation's documentation of enforced disappearance and detention is not there.

Consequences: do not ingest from this host, do not cite it as the organisation, and treat anything
already collected from it after this date as untrusted. This is the second Libya-relevant domain in
this inventory found in that state, after tax.gov.ly.

## Compromised placeholder

**pm.gov.ly**, the Government of National Unity site, serves a "الموقع تحت التطوير" placeholder with
an injected SEO link farm: a repeated gambling brand string and 189 outbound hosts. Cabinet
decisions are not published there. The government's decisions are at gnu.gov.ly instead, behind a
WordPress REST API with renamed paths (`/lefunot/` for wp-json), carrying 648 decision records
dated 2021 to September 2024, titles only with no body text and no attached PDF.

## Dead endpoint

**lsm.gov.ly** (Libyan Stock Market) 301-redirects to `http://41.208.106.218/`, which serves
nothing. The exchange's web presence is effectively defunct. Capital-market information should be
taken from the Libyan Capital Market Authority (lcma.gov.ly) and the Central Bank.

## Domains checked and not resolving

Probed and returning no response, so either retired or never established. Recorded to prevent
repeated checking: `planning.gov.ly`, `oil.gov.ly`, `education.gov.ly`, `interior.gov.ly`,
`justice.gov.ly`, `transport.gov.ly`, `housing.gov.ly`, `water.gov.ly`, `mlg.gov.ly`,
`ports.gov.ly`, `gecol.ly`, `mmra.gov.ly`, `libyanpost.ly`, `hcs.ly`, `hor.ly`, `ccmce.ly`,
`gaci.gov.ly`, `nca.gov.ly`, `ida.gov.ly`, `ppa.gov.ly`, `nplo.gov.ly`, `cdalibya.org`,
`akakusoil.com`, `sirteoil.com.ly`, `zueitina.ly`, `tripolicci.ly`, `lcsfs.org`.

Several of these are institutions that certainly exist — the General Electricity Company of Libya,
the Man-Made River Authority, the Ministry of Local Government, the High Council of State, the
Central Committee for Municipal Council Elections. They operate without a working public website, or
publish through Facebook pages instead. For a country where Facebook is the dominant institutional
publishing channel, that is itself a finding, and Phase 2 should decide whether social-media
publication is in scope as a source type.

## Reproducing the reachability check

```bash
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
while IFS=, read -r id _ _ _ url _; do
  [ "$id" = "source_id" ] && continue
  code=$(curl -s -o /dev/null -w "%{http_code}" -L --max-time 20 -A "$UA" "$url")
  echo "$id,$url,$code"
done < sources/libyan_sources.csv
```
