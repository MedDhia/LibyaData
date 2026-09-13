# OpenSanctions, Libyan subgraph

## Licence

The files in this directory are derived from **OpenSanctions**
(<https://www.opensanctions.org>), which licenses its data under
**Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)**.

That is a different licence from the rest of this repository. Anything derived
from these files inherits it:

- **Attribution is required.** Cite OpenSanctions, and the export version
  recorded in `SOURCE.json`.
- **Non-commercial use only.** Commercial use needs a licence from
  OpenSanctions directly (<https://www.opensanctions.org/licensing/>).

This is why the files sit under `data/external/` rather than `data/processed/`,
alongside the GADM-derived nighttime lights and the ODbL OpenStreetMap anchors.

## What the upstream data is, and is not

OpenSanctions aggregates and entity-resolves published lists. It is a record of
**what authorities and registries have stated**, not a finding about any person.

- A **PEP** designation means someone holds or held a prominent public function.
  It is a status marker used for due diligence. It is not an allegation of
  wrongdoing, and the same is true of `role.rca`, which marks a relative or
  close associate of such a person.
- A **sanctions** designation records that a named authority listed the entity.
  Designations are contested, are lifted, and differ between authorities; the
  `status`, `listing_date` and `end_date` columns in `libya_sanctions.csv` carry
  what the source says.
- Entity resolution merges records across lists and is not error-free. Two
  people with a common Libyan name can be merged, and one person can survive as
  two nodes. Treat identity as a claim with provenance, which is what the
  `datasets` and `source_urls` columns are for.

These are living people. The material is published, and public officials acting
in office are legitimately the subject of research, which is the basis on which
this repository includes it. It is still personal data about named individuals,
and it should be used as evidence about offices and institutions rather than as
a dossier on a person.

## Provenance

`SOURCE.json` records the OpenSanctions export version, the FollowTheMoney model
version, the retrieval date, and the upstream SHA-1 and local SHA-256 of every
bulk file read. `scripts/download_opensanctions.py` re-fetches them and refuses
to continue if a checksum does not match the upstream index.
