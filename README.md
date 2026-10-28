# MLUK Spatial and Infrastructure Data Project

This repository contains a spatial data platform and the IRIS Brandenburg water-protection ingestion assignment (Task 073).

## Task 073: Water-protection ingestion

The implementation is in [`task073/`](task073/). It reads Brandenburg water-protection zones from the published WFS, validates and transforms polygon geometries, maps only source-published attributes, and supports idempotent loading into an isolated staging schema. It does not write to production schemas.

See [task073/README.md](task073/README.md) for provenance, schema mapping, setup, run instructions, assumptions, and known service limitations. The quality report is in [task073/QUALITY_REPORT.md](task073/QUALITY_REPORT.md).

## Existing spatial dashboard

The `app/` and `ui/` directories contain the broader spatial data and dashboard code for facilities, energy assets, grid infrastructure, land values, site scoring, and deterministic news reporting. The Streamlit dashboard entry point is `ui/app.py`.

## Repository setup

Python dependencies are declared in `pyproject.toml`. Task 073 also provides a pinned, isolated dependency list and Docker setup under `task073/`.

Do not put credentials in source control. Use local environment configuration for database connections, and use only isolated staging resources when running ingestion work.
