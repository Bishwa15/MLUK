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
- A local native PostgreSQL 18 database with PostGIS 3.6.2 was provisioned. The successful live run reported fetched=2027, accepted=2027, rejected=0, loaded=2027, status=success, source CRS EPSG:25833, and destination CRS EPSG:25832. The first request using `application/json` was rejected by the WFS; changing the configured output format to the service-advertised `GEOJSON` resolved that issue. A transient database-host resolution problem was resolved by using `127.0.0.1`, and a JSONB parameter cast issue was corrected before the successful load.
- After a repeated ingestion, post-load SQL validation showed 2,027 table rows, 2,027 distinct composite keys, and 0 invalid geometries. The separate extent check returned `BOX(664245.7556748496 5701237.579068459,893047.9491073666 5934528.198640121)`. A GeoJSON export opened in geojson.io and displayed polygon shapes; feature properties were visible when selected. This was a manual visual check, not an integrated map UI test.
- Docker Desktop could not be used because virtualization is disabled. The Docker Compose configuration is included but was not exercised; live ingestion and database validation used native PostgreSQL 18/PostGIS 3.6.2.
- Upsert intentionally does not delete stale records if the source removes a feature; deletion/synchronization semantics need a separately agreed policy.
- Local credentials are stored in `.env`; `.env` and `config.local.toml` are excluded from version control. The shared example config contains no credentials.
- The service page advertises CRS EPSG:25833 as its default. The observed full response contained 2,027 features; all 2,027 were accepted and loaded in the reported run. The reported post-load validation found 0 invalid geometries and a repeat load retained 2,027 distinct composite keys. This confirms the tested snapshot, not future completeness or legal coverage beyond the returned source polygons.
