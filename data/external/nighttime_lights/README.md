# Nighttime lights, Libya, 1992–2022

Imported from [MedDhia/SatelliteImagery](https://github.com/MedDhia/SatelliteImagery)
at commit `7ee81d2`, by `scripts/import_nighttime_lights.py`. `SOURCE.json`
records the commit and a SHA-256 for every one of the 357 files.

The underlying dataset is **LRCC-DVNL**, a long-term global nighttime light
series at 1 km built to stay usable in low-light and dark-sky regions rather
than only in bright urban cores.

> Tang, H., Zhong, Y., Deng, J., Xia, H., & Wei, J. (2025). Global nighttime
> light dataset from 1992 to 2022 with focus on low-light areas.
> *Scientific Data*, 12, 971. <https://doi.org/10.1038/s41597-025-05246-8>
> · data <https://doi.org/10.7910/DVN/15IKI5>

Administrative boundaries are GADM 4.1 (gadm.org).

## Licence — read `NOTICE.md` before reusing anything here

This material is **not** under the licence covering the rest of this
repository. The boundaries are GADM 4.1, which permits academic and other
non-commercial use with attribution but **not** commercial use or
redistribution as boundary data; the imagery is best read as CC BY-NC-ND 4.0.
`NOTICE.md` is the upstream notice, copied here unchanged so the terms travel
with the files. Attribute as *administrative boundaries from GADM 4.1
(gadm.org)*.

## What is here

### `results/` — 5 tables and 31 rasters

| File | Rows | Content |
|---|---|---|
| `LBY_adm1_zonal.csv` | 682 | per shabiya per year: pixels, area, sum of lights, mean DN, light density |
| `LBY_inequality_series.csv` | 279 | per year: Gini, Theil T, Theil L, sum of lights, lit share |
| `LBY_theil_decomposition.csv` | 372 | Theil split into between- and within-shabiya components |
| `LBY_theil_by_unit.csv` | 3,472 | each shabiya's contribution to national Theil T |
| `LBY_adm1_aridity.csv` | 22 | aridity-zone shares per shabiya |
| `raster/LACC_YYYY_LBY.tif` | 31 files | annual rasters clipped to Libya, EPSG:8857, source dtype preserved |

### `figures/` — 321 images

31 annual maps in three palettes at two administrative levels, choropleths in
two palettes (absolute and relative scaling), small-multiple panels, and the
national inequality-series chart.

## Joining to the rest of this repository

The tables are keyed by GADM's romanised admin-1 names. The census is keyed by
its own. **Only 7 of the 22 agree** — GADM writes Darnah, Surt, Misratah and
Wadi ash Shati' where the census has Derna, Sirte, Misrata and Wadi al Shatii —
so a join on name silently drops two thirds of the country.

Use [`../../processed/concordance_shabiya.csv`](../../processed/concordance_shabiya.csv),
which maps all 22 units both ways:

```r
lights <- read.csv("data/external/nighttime_lights/results/LBY_adm1_zonal.csv")
cross  <- read.csv("data/processed/concordance_shabiya.csv")
census <- read.csv("data/processed/bsc_census_2006_shabiya.csv")

panel <- merge(merge(lights, cross, by.x = "name", by.y = "gadm_name"),
               census, by = "shabiya_ar")
```

That joins all 682 zonal rows, 1992 through 2022.

### The units share names, not boundaries

The two sources both divide Libya into 22 shabiyat and the mapping between them
is one-to-one, confirmed by ranking the units by area (Spearman 0.985). But
they are not the same polygons. Libya reorganised its administrative units after
2006, and the areas differ:

- 9 of 22 units agree within ±10%, 15 within ±25%
- national area differs by 3.6% (GADM 1,616,085 km² against the census's
  1,676,198 km²)
- Tripoli is the extreme: 2,435 km² in GADM against 835 km² in the census

So treat a lights-to-census join as matching **units by identity, not by
territory**. Per-unit ratios such as lights per head carry that boundary
mismatch, and it is largest exactly where population is densest.

### No admin-2 for Libya

GADM 4.1 has no ADM_2 layer for Libya, so the analysis stops at admin-1 and
there is no nested three-way Theil decomposition of the kind the upstream
repository shows for Tunisia. The census's 667 mahallas have no counterpart
here. That gap is in the boundary data, not an omission.

## Reading the figures and numbers

The upstream `results/README.md` sets out four cautions that apply in full:

1. **A lit pixel never dims — it goes out.** Every decrease is a lit-to-unlit
   transition, so gradual dimming is invisible and a falling Gini is partly
   imposed by the measure.
2. **2014 is a sensor handover** (DMSP to VIIRS) and a dtype change. Treat any
   2013→2014 step as a candidate artefact rather than a finding.
3. **DN is a relative index, not radiance.** A Gini of DN is not a Gini of
   income or output.
4. **`theil_l` is `nan` wherever any value is zero**, which is most
   zeros-included rows. The measure is undefined there; it is not a bug.

For Libya specifically, gas flaring dominates the sparsely populated oil
regions: Al Wahat records by far the highest lights per head in 2006, roughly
thirty-five times Tripoli's. That is flare stacks, not streetlights, and it is
the clearest reason not to read this series as a proxy for settlement,
prosperity or public service provision without further work.
