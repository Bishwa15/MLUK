import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from shapely.geometry import box, mapping

from water_protection.cli import _validate_database_url, _write_report
from water_protection.ingest import FieldMap, IngestionError, IngestionReport, fetch_features, inspect_capabilities, load_postgis, normalize_features, parcel_relation, UPSERT_SQL

FIXTURE = json.loads((Path(__file__).parents[1] / "fixtures" / "wfs_features.json").read_text(encoding="utf-8"))
FIELDS = FieldMap(
    source_id="GmlID", official_zone_id="ID_NR", wsg_id="WSG_ID", zone_code="CODE",
    zone_class="SCHUTZZONE", legal_effective_date="WSG_VOM", legal_reference="VO_TEXT",
    publication_reference="FUNDSTELLE",
)


def test_fixture_transforms_multipart_and_maps_only_source_fields():
    gdf, report = normalize_features(FIXTURE["features"], "EPSG:25833", FIELDS, "BB")
    assert report.fetched == 2 and report.accepted == 2 and report.rejected == 0
    assert gdf.crs.to_epsg() == 25832
    assert all(geometry.geom_type == "MultiPolygon" for geometry in gdf.geometry)
    assert gdf.iloc[0].zone_code == 20
    assert gdf.iloc[0].zone_class == "Zone II"
    assert gdf.iloc[0].official_zone_id == "7385200011"
    assert gdf.iloc[0].restriction_category is None
    assert gdf.iloc[0].extraction_rate is None
    assert gdf.iloc[0].source_updated_at is None


def test_missing_duplicate_ids_invalid_geometry_and_nonpolygon_are_rejected():
    good = FIXTURE["features"][0]
    features = [
        good,
        good,
        {"type": "Feature", "geometry": mapping(box(382300, 5806000, 382400, 5806100)), "properties": {}},
        {"type": "Feature", "geometry": None, "properties": {"GmlID": "no-geometry"}},
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [382300, 5806000]}, "properties": {"GmlID": "point"}},
        {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[382300, 5806000], [382400, 5806100], [382300, 5806100], [382400, 5806000], [382300, 5806000]]]}, "properties": {"GmlID": "invalid"}},
    ]
    gdf, report = normalize_features(features, "EPSG:25833", FIELDS, "BB")
    assert len(gdf) == 1
    assert report.rejected == 5
    assert any("duplicate ID" in message for message in report.errors)


def test_missing_declared_crs_is_never_guessed():
    with pytest.raises(IngestionError, match="refusing to guess"):
        normalize_features(FIXTURE["features"], "", FIELDS, "BB")


def test_fetch_validates_returned_crs_and_requests_configured_format():
    class Response:
        def __init__(self, payload): self.payload = payload
        def raise_for_status(self): pass
        def json(self): return self.payload

    class Session:
        def __init__(self, payload): self.payload = payload; self.calls = []
        def get(self, url, params, timeout): self.calls.append(params); return Response(self.payload)

    session = Session(FIXTURE)
    features, crs = fetch_features(session, "https://example.gov/wfs", "demo:layer", "EPSG:25833", page_size=10)
    assert len(features) == 2
    assert crs == "EPSG:25833"
    assert session.calls[0]["outputFormat"] == "GEOJSON"
    assert session.calls[0]["srsName"] == "EPSG:25833"

    bad = dict(FIXTURE)
    bad["crs"] = {"type": "name", "properties": {"name": "EPSG:4326"}}
    with pytest.raises(IngestionError, match="differs from requested"):
        fetch_features(Session(bad), "https://example.gov/wfs", "demo:layer", "EPSG:25833")


def test_fetch_uses_result_paging_until_all_features_are_returned():
    first = dict(FIXTURE)
    first["features"] = FIXTURE["features"]
    first["numberMatched"] = 3
    second_feature = dict(FIXTURE["features"][0])
    second_feature["properties"] = dict(second_feature["properties"], GmlID="Wasserschutzgebiete.59168")
    second = dict(FIXTURE, features=[second_feature], numberMatched=3)

    class Response:
        def __init__(self, payload): self.payload = payload
        def raise_for_status(self): pass
        def json(self): return self.payload

    class Session:
        def __init__(self): self.calls = []
        def get(self, url, params, timeout):
            self.calls.append(params)
            return Response(first if params["startIndex"] == 0 else second)

    session = Session()
    features, _ = fetch_features(session, "https://example.gov/wfs", "demo:layer", "EPSG:25833", page_size=2)
    assert len(features) == 3
    assert [call["startIndex"] for call in session.calls] == [0, 2]


def test_capabilities_discovery_reads_advertised_layer_and_default_crs():
    xml = b'''<?xml version="1.0"?><wfs:WFS_Capabilities xmlns:wfs="http://www.opengis.net/wfs/2.0" version="2.0.0"><wfs:FeatureTypeList><wfs:FeatureType><wfs:Name>wasser_wsg:Wasserschutzgebiete</wfs:Name><wfs:Title>Wasserschutzgebiete</wfs:Title><wfs:DefaultCRS>urn:ogc:def:crs:EPSG::25833</wfs:DefaultCRS></wfs:FeatureType></wfs:FeatureTypeList></wfs:WFS_Capabilities>'''

    class Response:
        content = xml
        def raise_for_status(self): pass

    class Session:
        def get(self, url, params, timeout): return Response()

    result = inspect_capabilities(Session(), "https://example.gov/wfs")
    assert result["version"] == "2.0.0"
    assert result["feature_types"] == [{"name": "wasser_wsg:Wasserschutzgebiete", "default_crs": "EPSG:25833", "title": "Wasserschutzgebiete"}]


def test_repeat_load_uses_composite_upsert_key_and_only_staging():
    gdf, _ = normalize_features(FIXTURE["features"][:1], "EPSG:25833", FIELDS, "BB", source_dataset_metadata_date="2026-10-09")

    class Cursor:
        def __init__(self): self.sql = []; self.rows = []
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def execute(self, sql): self.sql.append(sql)
        def executemany(self, sql, rows): self.sql.append(sql); self.rows.extend(rows)

    class Connection:
        def __init__(self): self.cur = Cursor(); self.commits = 0
        def cursor(self): return self.cur
        def commit(self): self.commits += 1

    connection = Connection()
    assert load_postgis(connection, gdf) == 1
    assert load_postgis(connection, gdf) == 1
    statements = " ".join(connection.cur.sql)
    assert "iris_staging.water_protection_zones" in statements
    assert "iris_core" not in statements
    assert "ON CONFLICT (source_zone_id,state_code) DO UPDATE" in statements
    assert {(row[0], row[1]) for row in connection.cur.rows} == {("Wasserschutzgebiete.59166", "BB")}
    assert all(len(row) == 18 for row in connection.cur.rows)
    assert "source_updated_at,source_dataset_metadata_date,source_attributes,source_crs" in UPSERT_SQL
    assert "%s,%s::jsonb,%s,%s,%s" in UPSERT_SQL
    assert connection.cur.rows[0][12] == "2026-10-09"
    assert json.loads(connection.cur.rows[0][13]) == FIXTURE["features"][0]["properties"]
    assert connection.cur.sql[-1].count("%s") == 18
    assert connection.commits == 2


def test_parcel_containment_intersection_and_outside():
    zone = box(0, 0, 10, 10)
    assert parcel_relation(zone, box(2, 2, 4, 4)) == "contained"
    assert parcel_relation(zone, box(9, 9, 11, 11)) == "intersects"
    assert parcel_relation(zone, box(12, 12, 14, 14)) == "outside"


def test_database_url_guard_and_run_report_capture_errors():
    _validate_database_url("postgresql://user:prod-password@localhost:5432/iris_local")
    with pytest.raises(IngestionError, match="core/production"):
        _validate_database_url("postgresql://user:password@localhost:5432/iris_core")
    with pytest.raises(IngestionError, match="core/production"):
        _validate_database_url("postgresql://user:password@production-db.internal:5432/iris_local")
    report = IngestionReport(status="error", errors=["sample failure"], source_url="https://example.gov/wfs")
    with TemporaryDirectory(dir=Path(__file__).parents[1]) as report_dir:
        path = _write_report(report, report_dir)
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved["status"] == "error"
        assert saved["errors"] == ["sample failure"]
        assert saved["source_url"] == "https://example.gov/wfs"
