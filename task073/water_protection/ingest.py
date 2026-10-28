from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
from typing import Any
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import geopandas as gpd
import requests
from pyproj import CRS
from shapely.geometry import MultiPolygon, shape

LOG = logging.getLogger(__name__)
TARGET_CRS = "EPSG:25832"
WFS_NS = {"wfs": "http://www.opengis.net/wfs/2.0"}


class IngestionError(RuntimeError):
    """Raised when WFS data cannot be safely interpreted or loaded."""


@dataclass(frozen=True)
class FieldMap:
    source_id: str
    official_zone_id: str | None = None
    wsg_id: str | None = None
    zone_code: str | None = None
    zone_class: str | None = None
    restriction_category: str | None = None
    extraction_rate: str | None = None
    legal_effective_date: str | None = None
    legal_reference: str | None = None
    publication_reference: str | None = None
    source_updated_at: str | None = None


@dataclass
class IngestionReport:
    fetched: int = 0
    accepted: int = 0
    rejected: int = 0
    loaded: int = 0
    empty: bool = False
    errors: list[str] = field(default_factory=list)
    fetched_at: str = ""
    source_crs: str = ""
    source_layer: str = ""
    source_url: str = ""
    source_dataset_metadata_date: str | None = None
    status: str = "started"


def _https_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("The WFS endpoint must be an explicit HTTPS URL")


def _crs_name(value: str) -> str:
    try:
        crs = CRS.from_user_input(value)
    except Exception as exc:
        raise IngestionError(f"Unrecognized declared CRS {value!r}") from exc
    if crs.to_epsg() is None:
        raise IngestionError(f"CRS {value!r} has no recognized EPSG code")
    return f"EPSG:{crs.to_epsg()}"


def inspect_capabilities(session: requests.Session, url: str, timeout: int = 30) -> dict[str, Any]:
    """Read WFS 2.0 metadata; fail on HTML, OWS exceptions, or missing layers."""
    _https_url(url)
    response = session.get(url, params={"service": "WFS", "request": "GetCapabilities", "version": "2.0.0"}, timeout=timeout)
    response.raise_for_status()
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as exc:
        raise IngestionError("GetCapabilities did not return XML") from exc
    if root.tag.endswith("ExceptionReport"):
        raise IngestionError("GetCapabilities returned an OWS exception")
    types = []
    for node in root.findall(".//wfs:FeatureType", WFS_NS):
        name = node.findtext("wfs:Name", default="", namespaces=WFS_NS)
        crs = node.findtext("wfs:DefaultCRS", default="", namespaces=WFS_NS)
        if not crs:
            crs = node.findtext("wfs:DefaultSRS", default="", namespaces=WFS_NS)
        types.append({
            "name": name,
            "default_crs": _crs_name(crs) if crs else "",
            "title": node.findtext("wfs:Title", default="", namespaces=WFS_NS),
        })
    if not types:
        raise IngestionError("GetCapabilities advertised no WFS feature types")
    return {"version": root.attrib.get("version", "unknown"), "feature_types": types}


def describe_feature_type(session: requests.Session, url: str, layer: str, timeout: int = 30) -> str:
    _https_url(url)
    response = session.get(url, params={
        "service": "WFS", "request": "DescribeFeatureType", "version": "2.0.0", "typeNames": layer,
    }, timeout=timeout)
    response.raise_for_status()
    return response.text


def fetch_features(
    session: requests.Session,
    url: str,
    layer: str,
    declared_crs: str,
    page_size: int = 500,
    timeout: int = 30,
    output_format: str = "GEOJSON",
) -> tuple[list[dict[str, Any]], str]:
    """Page WFS results and verify the CRS declared by each GeoJSON response."""
    _https_url(url)
    if page_size < 1:
        raise ValueError("page_size must be a positive integer")
    expected = _crs_name(declared_crs)
    all_features: list[dict[str, Any]] = []
    start = 0
    while True:
        response = session.get(url, params={
            "service": "WFS", "request": "GetFeature", "version": "2.0.0",
            "typeNames": layer, "outputFormat": output_format,
            "srsName": expected, "count": page_size, "startIndex": start,
        }, timeout=timeout)
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as exc:
            raise IngestionError(f"WFS returned non-JSON data at startIndex={start}") from exc
        if payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
            raise IngestionError(f"Unexpected WFS response at startIndex={start}: {str(payload)[:240]}")
        crs_obj = payload.get("crs") or {}
        crs_name = ((crs_obj.get("properties") or {}).get("name"))
        if not crs_name:
            raise IngestionError("GeoJSON response omitted its CRS; refusing to guess")
        actual = _crs_name(crs_name)
        if actual != expected:
            raise IngestionError(f"GeoJSON CRS {actual} differs from requested/declared {expected}")
        page = payload["features"]
        all_features.extend(page)
        matched = payload.get("numberMatched")
        try:
            matched_count = int(matched)
        except (TypeError, ValueError):
            matched_count = None
        if not page or len(page) < page_size or (matched_count is not None and len(all_features) >= matched_count):
            break
        start += len(page)
    return all_features, expected


def normalize_features(
    features: list[dict[str, Any]], source_crs: str, fields: FieldMap, state_code: str,
    source_layer: str = "wasser_wsg:Wasserschutzgebiete", fetched_at: str | None = None,
    source_dataset_metadata_date: str | None = None,
) -> tuple[gpd.GeoDataFrame, IngestionReport]:
    """Validate identifiers and multipart polygons, then transform to target CRS."""
    if not source_crs:
        raise IngestionError("WFS did not declare a source CRS; refusing to guess")
    if not fields.source_id:
        raise IngestionError("A verified source_id field mapping is required")
    source_crs = _crs_name(source_crs)
    report = IngestionReport(
        fetched=len(features), empty=not features,
        fetched_at=fetched_at or datetime.now(timezone.utc).isoformat(),
        source_crs=source_crs, source_layer=source_layer,
        source_dataset_metadata_date=source_dataset_metadata_date,
    )
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, feature in enumerate(features):
        props = feature.get("properties") or {}
        raw_id = props.get(fields.source_id)
        if raw_id is None or not str(raw_id).strip():
            report.rejected += 1
            report.errors.append(f"feature[{index}]: missing source ID field {fields.source_id}")
            continue
        source_id = str(raw_id).strip()
        if source_id in seen:
            report.rejected += 1
            report.errors.append(f"feature[{index}] {source_id}: duplicate ID within WFS response")
            continue
        raw_geometry = feature.get("geometry")
        if not raw_geometry:
            report.rejected += 1
            report.errors.append(f"feature[{index}] {source_id}: missing geometry")
            continue
        try:
            geometry = shape(raw_geometry)
            if geometry.is_empty or not geometry.is_valid:
                raise ValueError("empty or invalid geometry")
            if geometry.geom_type == "Polygon":
                geometry = MultiPolygon([geometry])
            if geometry.geom_type != "MultiPolygon":
                raise ValueError(f"unsupported geometry type {geometry.geom_type}")
        except Exception as exc:
            report.rejected += 1
            report.errors.append(f"feature[{index}] {source_id}: {exc}")
            continue
        seen.add(source_id)
        def mapped(key: str | None) -> Any:
            return props.get(key) if key else None
        records.append({
            "source_zone_id": source_id,
            "state_code": state_code,
            "official_zone_id": mapped(fields.official_zone_id),
            "wsg_id": mapped(fields.wsg_id),
            "zone_code": mapped(fields.zone_code),
            "zone_class": mapped(fields.zone_class),
            "restriction_category": mapped(fields.restriction_category),
            "extraction_rate": mapped(fields.extraction_rate),
            "legal_effective_date": mapped(fields.legal_effective_date),
            "legal_reference": mapped(fields.legal_reference),
            "publication_reference": mapped(fields.publication_reference),
            "source_updated_at": mapped(fields.source_updated_at),
            "source_dataset_metadata_date": source_dataset_metadata_date,
            "source_attributes": json.dumps(props, ensure_ascii=False, default=str),
            "source_crs": source_crs,
            "data_origin": f"Brandenburg WFS {source_layer}",
            "ingested_at": report.fetched_at,
            "geometry": geometry,
        })
    columns = [
        "source_zone_id", "state_code", "official_zone_id", "wsg_id", "zone_code", "zone_class",
        "restriction_category", "extraction_rate", "legal_effective_date", "legal_reference",
        "publication_reference", "source_updated_at", "source_dataset_metadata_date", "source_attributes", "source_crs", "data_origin",
        "ingested_at", "geometry",
    ]
    if records:
        gdf = gpd.GeoDataFrame(records, geometry="geometry", crs=source_crs).to_crs(TARGET_CRS)
    else:
        gdf = gpd.GeoDataFrame(columns=columns, geometry="geometry", crs=TARGET_CRS)
    report.accepted = len(gdf)
    return gdf, report


CREATE_SQL = """CREATE TABLE IF NOT EXISTS iris_staging.water_protection_zones (
 source_zone_id text NOT NULL,
 state_code text NOT NULL,
 official_zone_id text,
 wsg_id text,
 zone_code text,
 zone_class text,
 restriction_category text,
 extraction_rate text,
 legal_effective_date text,
 legal_reference text,
 publication_reference text,
 source_updated_at text,
 source_dataset_metadata_date text,
 source_attributes jsonb NOT NULL,
 source_crs text NOT NULL,
 data_origin text NOT NULL,
 ingested_at timestamptz NOT NULL,
 geom geometry(MultiPolygon, 25832) NOT NULL,
 PRIMARY KEY (source_zone_id, state_code)
)"""

UPSERT_SQL = """INSERT INTO iris_staging.water_protection_zones (
 source_zone_id,state_code,official_zone_id,wsg_id,zone_code,zone_class,
 restriction_category,extraction_rate,legal_effective_date,legal_reference,
 publication_reference,source_updated_at,source_dataset_metadata_date,source_attributes,source_crs,data_origin,ingested_at,geom
) VALUES (
 %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,ST_Multi(ST_GeomFromWKB(%s,25832))
)
ON CONFLICT (source_zone_id,state_code) DO UPDATE SET
 official_zone_id=EXCLUDED.official_zone_id,wsg_id=EXCLUDED.wsg_id,
 zone_code=EXCLUDED.zone_code,zone_class=EXCLUDED.zone_class,
 restriction_category=EXCLUDED.restriction_category,extraction_rate=EXCLUDED.extraction_rate,
 legal_effective_date=EXCLUDED.legal_effective_date,legal_reference=EXCLUDED.legal_reference,
 publication_reference=EXCLUDED.publication_reference,source_updated_at=EXCLUDED.source_updated_at,
 source_dataset_metadata_date=EXCLUDED.source_dataset_metadata_date,
 source_attributes=EXCLUDED.source_attributes,source_crs=EXCLUDED.source_crs,
 data_origin=EXCLUDED.data_origin,ingested_at=EXCLUDED.ingested_at,geom=EXCLUDED.geom"""


def load_postgis(connection: Any, gdf: gpd.GeoDataFrame) -> int:
    """Create/upsert only the assignment's staging table."""
    with connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        cursor.execute("CREATE SCHEMA IF NOT EXISTS iris_staging")
        cursor.execute(CREATE_SQL)
        rows = []
        for _, row in gdf.iterrows():
            rows.append((
                row.source_zone_id, row.state_code, row.official_zone_id, row.wsg_id,
                row.zone_code, row.zone_class, row.restriction_category, row.extraction_rate,
                row.legal_effective_date, row.legal_reference, row.publication_reference,
                row.source_updated_at, row.source_dataset_metadata_date, row.source_attributes, row.source_crs, row.data_origin,
                row.ingested_at, bytes(row.geometry.wkb),
            ))
        if rows:
            cursor.executemany(UPSERT_SQL, rows)
    connection.commit()
    return len(rows)


def parcel_relation(zone_geometry: Any, parcel_geometry: Any) -> str:
    """Classify full containment, boundary/partial intersection, or outside."""
    if zone_geometry.covers(parcel_geometry):
        return "contained"
    if zone_geometry.intersects(parcel_geometry):
        return "intersects"
    return "outside"
