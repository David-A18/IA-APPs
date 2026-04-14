"""Config loader and JSON Schema validator."""

from pathlib import Path

import jsonschema
import yaml


def load_yaml(path: Path) -> dict:
    """Load YAML file and return parsed dict."""
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_schema(schema_path: Path) -> dict:
    """Load JSON Schema from file."""
    import json

    with schema_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_config(config: dict, schema: dict) -> None:
    """Validate config dict against JSON Schema. Raises ConfigValidationError on failure."""
    validator = jsonschema.Draft7Validator(schema)
    errors = list(validator.iter_errors(config))
    if errors:
        messages = [f"  - {e.json_path}: {e.message}" for e in errors]
        raise ConfigValidationError("Config validation failed:\n" + "\n".join(messages))


def load_and_validate_config(
    settings_path: Path,
    schema_path: Path,
) -> dict:
    """Load settings.yaml and validate against config_schema.json."""
    config = load_yaml(settings_path)
    schema = load_schema(schema_path)
    validate_config(config, schema)
    return config


class ConfigValidationError(ValueError):
    """Raised when settings.yaml fails JSON Schema validation."""
