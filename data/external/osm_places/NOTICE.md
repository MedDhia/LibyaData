# Third-party terms for this directory

`mahalla_osm_anchors.csv` is derived from **OpenStreetMap**, obtained as
[Populated Places of Libya](https://data.humdata.org/dataset/hotosm_lby_populated_places)
via the Humanitarian OpenStreetMap Team.

> © OpenStreetMap contributors, available under the
> [Open Database License](https://opendatacommons.org/licenses/odbl/) (ODbL 1.0).

ODbL is share-alike. A database built from OSM data and made public carries the
same terms, so this file does, and the rest of this repository does not. It is
kept here rather than in `data/processed/` for exactly that reason: the
concordance itself contains no OSM-derived content, so it stays unencumbered.

Attribute as: *place coordinates © OpenStreetMap contributors, ODbL*.

The shabiya each place sits in comes from the COD-AB `adm2_pcode` already
carried on the OSM feature. COD-AB is CC BY-IGO; see
[`../../raw/hdx/`](../../raw/hdx/) and `scripts/download_hdx_codab.sh`.
