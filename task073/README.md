# Task 073 — Brandenburg Water Protection (MLUK)

This isolated module downloads Brandenburg water-protection polygons from the state WFS, validates source IDs and polygon geometry, transforms to EPSG:25832, and upserts only into `iris_staging.water_protection_zones`. It does not access `iris_core` or a production database.

## Verified source and assignment discrepancy

The attached specification names `https://inspire.brandenburg.de/services/wsg_wfs` and layer `bb_wsg_portal`. That URL returned the Brandenburg INSPIRE portal HTML page during this review, not WFS XML. The official Brandenburg Geoportal lists the reachable WFS at `https://maps.brandenburg.de/services/wfs/wsg`; its capabilities advertise WFS 2.0, layer `wasser_wsg:Wasserschutzgebiete`, default CRS EPSG:25833, result paging, and GeoJSON output. The official feature type differs from the assignment's layer name, so the implementation uses the verified official service and reports the mismatch. No layer alias or hidden endpoint is guessed.

The source schema was verified with `DescribeFeatureType` and a small read-only GetFeature request. Returned attributes include `GmlID`, `OBJECTID`, `ID_NR`, `CODE`, `SCHUTZZONE`, `WSG_ID`, `FUNDSTELLE`, `WSG_VOM`, `DURCH`, and `VO_TEXT`. The importer maps `SCHUTZZONE` and `CODE` directly from those source fields. It preserves `ID_NR`, `WSG_ID`, legal reference, effective date, publication reference, and all raw properties. The source does not publish an extraction-rate or restriction-category field, nor a source-update timestamp; those destination fields remain `NULL`. `WSG_VOM` is a legal effective date and is not misrepresented as a data update date.

The service metadata states that no access restriction applies and specifies attribution to Landesamt für Umwelt Brandenburg under Datenlizenz Deutschland Namensnennung 2.0. The linked dataset record names CC BY 4.0, so the service and dataset metadata have different license labels; confirm the provider's applicable terms before redistributing data. The service metadata date is 9 July 2026; the linked dataset metadata is dated 9 October 2026. Runtime records each retrieval time. These metadata dates are not claimed to be feature-level update dates.

Source records: [WFS service metadata](https://geoportal.brandenburg.de/detailansichtdienst/render?url=https%3A%2F%2Fgeoportal.brandenburg.de%2Fgs-json%2Fxml%3Ffileid%3D4454b379-25e5-41bb-9075-a323b2f0ba3d&view=gdibb), [water-protection dataset metadata](https://geoportal.brandenburg.de/detailansichtdienst/render?url=https%3A%2F%2Fgeoportal.brandenburg.de%2Fgs-json%2Fxml%3Ffileid%3D657B712B-9009-49C0-8C91-A373AA87291A), and [WFS GetCapabilities](https://maps.brandenburg.de/services/wfs/wsg?request=GetCapabilities&service=WFS).

## Quick start

Python 3.11 or newer is required. Run the following commands from this `task073` directory. Install the pinned dependencies and run the fixture tests:

```sh
python -m pip install -r requirements.txt
python -m pytest -q
```

Inspect the live service and its layer schema (read-only):

```sh
python -m water_protection.cli inspect --config config.example.toml
```

For the isolated local PostGIS instance, set local credentials in the shell; do not commit them:

```powershell
$env:POSTGRES_DB = "iris_local"
$env:POSTGRES_USER = "iris_staging"
$env:POSTGRES_PASSWORD = "<choose-a-local-password>"
docker compose up -d postgis
```

Then use the importer profile, which connects only to that compose database:

```sh
docker compose --profile ingest run --rm importer ingest --config /app/config.example.toml
```

Each ingestion attempt writes a timestamped JSON run report under `run_reports/`, including empty/error status, rejection details, source metadata date, and retrieval time. Docker Compose bind-mounts that directory so reports remain available on the host.

For a separately provisioned staging database, set `DATABASE_URL` to a staging-only account. Never use production credentials. The CLI refuses database names that identify `iris_core`, `prod`, or `production`; this check is a guardrail, not a substitute for least-privilege credentials.

## Mapping and loading

| Destination field | Verified source or rule |
| --- | --- |
| `source_zone_id` | `GmlID` feature identifier returned by the WFS |
| `official_zone_id` | `ID_NR` |
| `wsg_id` | `WSG_ID` |
| `zone_code` | `CODE`, preserved as published |
| `zone_class` | `SCHUTZZONE`, preserved as published (for example `Zone II`) |
| `restriction_category` | `NULL`; no such source field was published |
| `extraction_rate` | `NULL`; no such source field was published |
| `legal_effective_date` | `WSG_VOM` |
| `legal_reference` | `VO_TEXT` |
| `publication_reference` | `FUNDSTELLE` |
| `source_updated_at` | `NULL`; no source update field was published |
| `source_attributes` | All feature properties as JSONB |
| `source_crs`, `data_origin`, `ingested_at` | Captured on each retrieval |
| `geom` | Valid Polygon/MultiPolygon converted to MultiPolygon and transformed from EPSG:25833 to EPSG:25832 |

The WFS GeoJSON response was observed as EPSG:4326 when no `srsName` was supplied. Supplying the advertised default `srsName=EPSG:25833` returned coordinates and GeoJSON CRS in EPSG:25833. The importer always requests that CRS, then verifies the response CRS before transformation. Pagination uses WFS 2.0 `count` and `startIndex`.

Rows are idempotently upserted with a primary key on `(source_zone_id, state_code)`. Features missing IDs, with duplicate IDs in one response, missing geometries, invalid/empty geometries, or unsupported geometry types are rejected and counted in the run report. No invalid geometry repair is attempted.

The upsert does not delete rows that the source later removes; a production synchronization process would need an explicit, reviewed stale-row policy. The current module never deletes destination records.

## Parcel screening example

```python
from shapely.geometry import shape
from water_protection.ingest import parcel_relation

relation = parcel_relation(zone_geometry, parcel_geometry)
# "contained", "intersects", or "outside"
```

Example PostGIS validation query:

```sql
SELECT state_code, source_crs, data_origin,
       count(*) AS zones,
       count(*) FILTER (WHERE zone_class IS NULL) AS unknown_class,
       count(*) FILTER (WHERE restriction_category IS NULL) AS unknown_restriction,
       count(*) FILTER (WHERE extraction_rate IS NULL) AS unknown_extraction_rate,
       min(ingested_at) AS first_ingested, max(ingested_at) AS last_ingested
FROM iris_staging.water_protection_zones
WHERE state_code = 'BB'
GROUP BY state_code, source_crs, data_origin;
```

## Limitations

- The live WFS has been checked for capabilities, schema, CRS, GeoJSON format, and a small set of features. A full dataset load into PostGIS was not run in this workspace because no staging database credentials were provided.
- The assignment's named endpoint/layer do not match the current official Geoportal service. The implementation uses the official reachable WFS and records the discrepancy; a reviewer should confirm that this is the expected service mapping.
- Restrictions applicable to a parcel depend on the individual water-protection order and other laws. `VO_TEXT` links to legal orders, but restriction categories and extraction rates are not present as structured WFS attributes and are intentionally not inferred.
- The fixture geometries are representative test shapes in EPSG:25833; source-like attributes follow the verified schema. They are not presented as copies of the live polygons.
- Invalid geometries are rejected, not repaired. The catalog extent is approximately 11.4285–14.7434° E and 51.3459–53.4672° N. The importer does not claim that a parcel outside a returned polygon has no other legal restrictions.
- The composite key uses the WFS-returned `GmlID` feature identifier; the official zone reference `ID_NR` is retained separately. The service does not document a stability guarantee for `GmlID` across dataset republishing.
