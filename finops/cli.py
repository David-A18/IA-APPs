"""FinOps Autopilot CLI — main entrypoint."""

from __future__ import annotations

import json
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
_DEFAULT_RULES = Path(__file__).parent / "config" / "rules" / "anomaly_rules.yaml"
_DEFAULT_DB = Path("finops.duckdb")


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
    config: Path = typer.Option(_DEFAULT_CONFIG, "--config", "-c"),
    schema: Path = typer.Option(_DEFAULT_SCHEMA, "--schema", "-s"),
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
    source: str = typer.Argument(help="Local CSV path or s3://bucket/key"),
    db: Path = typer.Option(_DEFAULT_DB, "--db"),
    region: str = typer.Option("us-east-1", "--region", "-r"),
) -> None:
    """Ingest CUR data from local CSV or S3 into DuckDB."""
    from finops.ingestion.cur_parser import parse_cur_from_file, parse_cur_from_s3
    from finops.ingestion.cur_enricher import enrich_cur_rows
    from finops.ingestion.local_store import LocalStore

    console.print(f"[bold]Source:[/bold] {source}")
    with console.status("Parsing CUR..."):
        if source.startswith("s3://"):
            parts = source[5:].split("/", 1)
            bucket, key = parts[0], parts[1] if len(parts) > 1 else ""
            rows = parse_cur_from_s3(bucket, key, region)
        else:
            rows = parse_cur_from_file(Path(source))

    console.print(f"  Parsed [cyan]{len(rows)}[/cyan] line items")
    with console.status("Enriching + storing..."):
        enriched = enrich_cur_rows(rows)
        store = LocalStore(db)
        count = store.insert_cur_rows(enriched)
        store.close()

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Line items parsed", str(len(rows)))
    table.add_row("Rows stored", str(count))
    table.add_row("Database", str(db))
    console.print(table)


@app.command()
def anomalies(
    db: Path = typer.Option(_DEFAULT_DB, "--db"),
    end_date: str = typer.Option("", "--date", "-d", help="Check date (YYYY-MM-DD). Defaults to latest."),
    lookback: int = typer.Option(7, "--lookback", "-l", help="Lookback window in days"),
    rules: Path = typer.Option(_DEFAULT_RULES, "--rules"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table | json"),
) -> None:
    """Detect cost anomalies using configured rules."""
    from finops.ingestion.local_store import LocalStore
    from finops.analysis.anomaly_detector import detect_anomalies

    with LocalStore(db) as store:
        events = detect_anomalies(
            store,
            rules_path=rules,
            end_date=end_date or None,
            lookback_days=lookback,
        )

    if not events:
        console.print("[green]No anomalies detected.[/green]")
        return

    if output == "json":
        console.print(json.dumps([e.as_dict() for e in events], indent=2))
        return

    table = Table(title=f"Anomalies detected: {len(events)}", header_style="bold red")
    table.add_column("Severity", width=8)
    table.add_column("Rule")
    table.add_column("Service/Region")
    table.add_column("Date", width=12)
    table.add_column("Delta $", justify="right")
    table.add_column("Delta %", justify="right")

    severity_color = {"high": "red", "medium": "yellow", "low": "cyan"}
    for e in events:
        color = severity_color.get(e.severity, "white")
        subject = e.service or e.region or "total"
        pct = f"+{e.delta_pct:.1f}%" if e.delta_pct else "new"
        table.add_row(
            f"[{color}]{e.severity}[/{color}]",
            e.rule_name,
            subject,
            e.detected_date,
            f"${e.delta_usd:+.2f}",
            pct,
        )
    console.print(table)


@app.command(name="top-movers")
def top_movers(
    db: Path = typer.Option(_DEFAULT_DB, "--db"),
    current_start: str = typer.Argument(help="Current period start (YYYY-MM-DD)"),
    current_end: str = typer.Argument(help="Current period end (YYYY-MM-DD)"),
    previous_start: str = typer.Option("", "--prev-start"),
    previous_end: str = typer.Option("", "--prev-end"),
    top_n: int = typer.Option(10, "--top", "-n"),
    output: str = typer.Option("table", "--output", "-o"),
) -> None:
    """Show services with the biggest cost changes between two periods."""
    from finops.ingestion.local_store import LocalStore
    from finops.analysis.top_movers import compute_top_movers

    with LocalStore(db) as store:
        result = compute_top_movers(
            store,
            current_start=current_start,
            current_end=current_end,
            previous_start=previous_start or None,
            previous_end=previous_end or None,
            top_n=top_n,
        )

    if output == "json":
        console.print(json.dumps(result, indent=2))
        return

    period = result["period"]
    console.print(
        f"\n[bold]Current:[/bold] {period['current']['start']} → {period['current']['end']}"
    )
    console.print(
        f"[bold]Previous:[/bold] {period['previous']['start']} → {period['previous']['end']}\n"
    )

    for label, movers in [("By Absolute Change ($)", result["by_absolute"]),
                           ("By Percentage Change (%)", result["by_percentage"])]:
        table = Table(title=label, header_style="bold magenta")
        table.add_column("Service")
        table.add_column("Current $", justify="right")
        table.add_column("Previous $", justify="right")
        table.add_column("Delta $", justify="right")
        table.add_column("Delta %", justify="right")
        table.add_column("New?", justify="center")
        for m in movers:
            pct = f"+{m['delta_pct']:.1f}%" if m["delta_pct"] is not None else "—"
            table.add_row(
                m["service"],
                f"${m['current_cost_usd']:.2f}",
                f"${m['previous_cost_usd']:.2f}",
                f"${m['delta_usd']:+.2f}",
                pct,
                "✓" if m["is_new"] else "",
            )
        console.print(table)


@app.command(name="unit-economics")
def unit_economics(
    db: Path = typer.Option(_DEFAULT_DB, "--db"),
    start_date: str = typer.Argument(help="Start date (YYYY-MM-DD)"),
    end_date: str = typer.Argument(help="End date (YYYY-MM-DD)"),
    top_n: int = typer.Option(10, "--top", "-n"),
    output: str = typer.Option("table", "--output", "-o"),
) -> None:
    """Show cost breakdown by team, environment, category, and region."""
    from finops.ingestion.local_store import LocalStore
    from finops.analysis.unit_economics import compute_unit_economics

    with LocalStore(db) as store:
        report = compute_unit_economics(store, start_date, end_date, top_n)

    if output == "json":
        console.print(json.dumps(report.as_dict(), indent=2))
        return

    console.print(
        f"\n[bold]Total cost:[/bold] [green]${report.total_cost:.2f}[/green] "
        f"({start_date} → {end_date})\n"
    )

    sections = [
        ("By Team", "cost_owner", report.by_team),
        ("By Environment", "environment", report.by_environment),
        ("By Category", "service_category", report.by_category),
        ("By Region", "region", report.by_region),
    ]

    for title, key_col, rows in sections:
        table = Table(title=title, header_style="bold cyan")
        table.add_column(title.split(" ")[1])
        table.add_column("Cost ($)", justify="right")
        table.add_column("%", justify="right")
        for row in rows:
            label = row.get(key_col) or row.get("cost_owner") or row.get("environment") or "—"
            table.add_row(label, f"${row['total_cost']:.2f}", f"{row['pct_of_total']:.1f}%")
        console.print(table)

    table = Table(title="Top Services", header_style="bold yellow")
    table.add_column("Service")
    table.add_column("Cost ($)", justify="right")
    table.add_column("Line Items", justify="right")
    for row in report.top_services:
        table.add_row(row["product_name"], f"${row['total_cost']:.2f}", str(row["line_items"]))
    console.print(table)


if __name__ == "__main__":
    app()
