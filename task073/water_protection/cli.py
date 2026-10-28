from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import tomllib
from urllib.parse import unquote, urlparse

import requests

from .ingest import (
    FieldMap,
    IngestionError,
    IngestionReport,
    describe_feature_type,
    fetch_features,
    inspect_capabilities,
    load_postgis,
    normalize_features,
)


def _validate_database_url(value: str) -> None:
    parsed = urlparse(value)
    database = unquote(parsed.path.lstrip("/")).lower()
    hostname = (parsed.hostname or "").lower()
    unsafe_database = database in {"iris_core", "prod", "production"} or database.endswith(("_prod", "_production"))
    unsafe_host = any(
        label in {"prod", "production", "iris-core"}
        or label.startswith(("prod-", "production-"))
        or label.endswith(("-prod", "-production"))
        for label in hostname.split(".")
    )
    if unsafe_database or unsafe_host:
        raise IngestionError("Refusing a database URL that appears to target core/production")


def _write_report(report: IngestionReport, directory: str) -> Path:
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = target / f"run-{timestamp}.json"
    path.write_text(json.dumps(asdict(report), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="IRIS Task 073 Brandenburg water protection ingestion")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("inspect", "ingest"):
        item = sub.add_parser(command)
        item.add_argument("--config", required=True)
    args = parser.parse_args()
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    cfg = tomllib.loads(Path(args.config).read_text(encoding="utf-8"))
    session = requests.Session()
    url = cfg["wfs_url"]
    layer = cfg["layer_name"]
    timeout = int(cfg.get("timeout_seconds", 30))
    report_directory = os.environ.get("REPORT_DIRECTORY", cfg.get("report_directory", "run_reports"))

    if args.command == "inspect":
        capabilities = inspect_capabilities(session, url, timeout)
        print(json.dumps(capabilities, indent=2))
        layer_info = next((item for item in capabilities["feature_types"] if item["name"] == layer), None)
        if not layer_info:
            raise IngestionError(f"Configured layer {layer!r} is not advertised by the service")
        print(describe_feature_type(session, url, layer, timeout))
        return

    report = IngestionReport(
        fetched_at=datetime.now(timezone.utc).isoformat(), source_layer=layer,
        source_url=url, source_dataset_metadata_date=cfg.get("source_dataset_metadata_date"),
    )
    try:
        capabilities = inspect_capabilities(session, url, timeout)
        layer_info = next((item for item in capabilities["feature_types"] if item["name"] == layer), None)
        if not layer_info:
            raise IngestionError(f"Configured layer {layer!r} is not advertised by the service")
        report.source_crs = layer_info["default_crs"]
        describe_feature_type(session, url, layer, timeout)
        fields = FieldMap(**{key: (value or None) for key, value in cfg["fields"].items()})
        features, response_crs = fetch_features(
            session, url, layer, report.source_crs,
            page_size=int(cfg.get("page_size", 500)), timeout=timeout,
            output_format=cfg.get("output_format", "GEOJSON"),
        )
        report.fetched = len(features)
        report.source_crs = response_crs
        gdf, report = normalize_features(
            features, response_crs, fields, cfg["state_code"], layer,
            fetched_at=report.fetched_at,
            source_dataset_metadata_date=cfg.get("source_dataset_metadata_date"),
        )
        report.source_url = url
        if not features:
            report.status = "empty"
            report.errors.append("WFS returned an empty FeatureCollection; staging load contains zero rows")
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise IngestionError("DATABASE_URL is required for ingest; use an isolated staging database")
        _validate_database_url(database_url)
        import psycopg
        with psycopg.connect(database_url) as connection:
            report.loaded = load_postgis(connection, gdf)
        if report.status != "empty":
            report.status = "completed_with_rejections" if report.rejected else "success"
    except Exception as exc:
        report.status = "error"
        report.errors.append(f"{type(exc).__name__}: {exc}")
        report_path = _write_report(report, report_directory)
        print(json.dumps({**asdict(report), "report_file": str(report_path)}, indent=2, ensure_ascii=False))
        raise

    report_path = _write_report(report, report_directory)
    print(json.dumps({**asdict(report), "report_file": str(report_path)}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
