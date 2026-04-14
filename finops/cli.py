"""FinOps Autopilot CLI — main entrypoint."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="finops",
    help="FinOps Autopilot — AWS cost anomaly detection and rightsizing.",
    no_args_is_help=True,
)
console = Console()

_DEFAULT_CONFIG = Path(__file__).parent / "config" / "settings.yaml"
_DEFAULT_SCHEMA = Path(__file__).parent / "config" / "schemas" / "config_schema.json"


@app.command()
def version() -> None:
    """Print version and exit."""
    from importlib.metadata import version as pkg_version

    try:
        v = pkg_version("finops-autopilot")
    except Exception:
        v = "0.1.0-dev"
    console.print(f"finops-autopilot [bold green]{v}[/bold green]")


@app.command(name="validate-config")
def validate_config(
    config: Path = typer.Option(_DEFAULT_CONFIG, "--config", "-c", help="Path to settings.yaml"),
    schema: Path = typer.Option(_DEFAULT_SCHEMA, "--schema", "-s", help="Path to config_schema.json"),
) -> None:
    """Validate settings.yaml against JSON Schema."""
    from finops.utils.validators import load_and_validate_config, ConfigValidationError

    try:
        load_and_validate_config(config, schema)
        console.print(f"[green]✓[/green] Config valid: {config}")
    except FileNotFoundError as e:
        console.print(f"[red]✗[/red] File not found: {e}")
        raise typer.Exit(1)
    except ConfigValidationError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(1)


@app.command()
def ingest(
    source: str = typer.Argument(help="Local CSV file path or s3://bucket/key"),
    config: Path = typer.Option(_DEFAULT_CONFIG, "--config", "-c", help="Path to settings.yaml"),
    db: Path = typer.Option(Path("finops.duckdb"), "--db", help="DuckDB file path (or :memory:)"),
    region: str = typer.Option("us-east-1", "--region", "-r", help="AWS region"),
) -> None:
    """Ingest CUR data from local CSV or S3 into local DuckDB store."""
    from finops.ingestion.cur_parser import parse_cur_from_file, parse_cur_from_s3
    from finops.ingestion.cur_enricher import enrich_cur_rows
    from finops.ingestion.local_store import LocalStore

    console.print(f"[bold]Ingesting CUR data from:[/bold] {source}")

    with console.status("Parsing CUR..."):
        if source.startswith("s3://"):
            parts = source[5:].split("/", 1)
            bucket, key = parts[0], parts[1] if len(parts) > 1 else ""
            rows = parse_cur_from_s3(bucket, key, region)
        else:
            rows = parse_cur_from_file(Path(source))

    console.print(f"  Parsed [cyan]{len(rows)}[/cyan] line items")

    with console.status("Enriching rows..."):
        enriched = enrich_cur_rows(rows)

    with console.status(f"Storing to {db}..."):
        store = LocalStore(db)
        count = store.insert_cur_rows(enriched)
        store.close()

    console.print(f"  [green]✓[/green] Inserted [cyan]{count}[/cyan] rows into [bold]{db}[/bold]")

    # Quick summary table
    table = Table(title="Ingestion Summary", show_header=True, header_style="bold magenta")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Total line items", str(len(rows)))
    table.add_row("Enriched rows", str(len(enriched)))
    table.add_row("Stored to DB", str(count))
    console.print(table)


if __name__ == "__main__":
    app()
