"""Shared pytest fixtures."""

from pathlib import Path

import pytest

from finops.ingestion.cur_parser import parse_cur_from_file
from finops.ingestion.cur_enricher import enrich_cur_rows
from finops.ingestion.local_store import LocalStore

FIXTURES_DIR = Path(__file__).parent / "fixtures"
CONFIG_DIR = Path(__file__).parent.parent / "finops" / "config"


@pytest.fixture
def sample_cur_path() -> Path:
    return FIXTURES_DIR / "sample_cur.csv"


@pytest.fixture
def sample_cur_rows(sample_cur_path: Path) -> list[dict]:
    return parse_cur_from_file(sample_cur_path)


@pytest.fixture
def enriched_cur_rows(sample_cur_rows: list[dict]) -> list[dict]:
    return enrich_cur_rows(sample_cur_rows)


@pytest.fixture
def in_memory_store(enriched_cur_rows: list[dict]) -> LocalStore:
    """In-memory DuckDB store pre-loaded with sample data."""
    store = LocalStore()
    store.insert_cur_rows(enriched_cur_rows)
    return store


@pytest.fixture
def sample_config() -> dict:
    import yaml

    with (CONFIG_DIR / "settings.yaml").open() as f:
        return yaml.safe_load(f)


@pytest.fixture
def config_schema() -> dict:
    import json

    with (CONFIG_DIR / "schemas" / "config_schema.json").open() as f:
        return json.load(f)
