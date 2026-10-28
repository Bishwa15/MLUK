# Task 073 quality and error report

## Source checks

- **Assignment endpoint:** `https://inspire.brandenburg.de/services/wsg_wfs` returned HTTP 200 with `text/html` for GetCapabilities, showing the INSPIRE portal landing page rather than WFS metadata.
- **Official Geoportal service:** `https://maps.brandenburg.de/services/wfs/wsg?request=GetCapabilities&service=WFS` returned WFS 2.0 XML and advertised `wasser_wsg:Wasserschutzgebiete`, default CRS EPSG:25833, result paging, and GeoJSON output. Geoportal metadata reports the service as reachable with no access restrictions and identifies Landesamt für Umwelt Brandenburg as the data source.
- **Provenance terms:** WFS service metadata lists Datenlizenz Deutschland Namensnennung 2.0; the linked dataset record lists CC BY 4.0. Both identify LfU Brandenburg attribution, but the metadata labels differ and should be confirmed before redistribution.
- **Schema check:** DescribeFeatureType confirmed `ID_NR`, `CODE`, `SCHUTZZONE`, `WSG_ID`, `FUNDSTELLE`, `WSG_VOM`, `DURCH`, `VO_TEXT`, and geometry. A read-only sample GetFeature request confirmed `GmlID` is returned in properties and showed `CODE=20` paired with `SCHUTZZONE=Zone II`, and `CODE=10` paired with `Zone I`.
- **CRS check:** Default GeoJSON without an explicit SRS was EPSG:4326. With `srsName=EPSG:25833`, the service returned GeoJSON coordinates in EPSG:25833. The importer requests and checks EPSG:25833 before transforming to EPSG:25832.

## Quality controls implemented

- Exact source field mappings preserve `CODE` and `SCHUTZZONE`; no substring classification rules are used.
- Missing IDs, response-local duplicate IDs, missing geometry, invalid/empty polygons, and non-polygon geometry are reported as rejected records.
- Accepted geometries are normalized to MultiPolygon and transformed using the declared WFS CRS.
- The staging table uses a composite primary key and `ON CONFLICT ... DO UPDATE`; tests call the loader repeatedly and check the generated SQL target/key.
- Parcel checks distinguish full coverage (`covers`), partial/boundary intersection, and outside.
- Fixture suite result: **9 passed**. The run covers direct field mapping, unknown values, CRS mismatch refusal, paging, rejected geometries/IDs, duplicate-key upsert SQL, safety guard, run-report output, and parcel relations.

## Unknowns and limitations

- `restriction_category`, `extraction_rate`, and a source data-update timestamp are absent from the published WFS fields and remain NULL. `WSG_VOM` is mapped only as the legal effective date.
- The PDF says Task 073 / IRIS-WSG-BB but names `bb_wsg_portal`; the live state service exposes `wasser_wsg:Wasserschutzgebiete`. The mismatch is documented for reviewer confirmation.
- The WFS service metadata and its linked dataset record use different license labels; confirm the provider's applicable terms before redistribution.
- No database credentials were supplied; no database connection or full PostGIS load was attempted. Tests use fixture/mock data and confirm the staging-only idempotent SQL.
- Docker CLI is unavailable in the current environment, so `docker compose config` and a local PostGIS runtime could not be checked. The tests do not claim an actual PostgreSQL duplicate-load result.
- Upsert intentionally does not delete stale records if the source removes a feature; deletion/synchronization semantics need a separately agreed policy.
- The base repository's Compose file had a hard-coded pgAdmin default password. It now reads credentials from environment variables; `.env.example` contains placeholders only and `.env` is ignored.
- The service page advertises CRS EPSG:25833 as its default. Full dataset coverage counts, validity distribution, and a full repeat-load result remain unmeasured pending staging execution.
