"""FinOps Autopilot CLI — main entrypoint."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from finops import __version__

app = typer.Typer(
    name="finops",
    help="FinOps Autopilot — AWS cost anomaly detection and rightsizing.",
    no_args_is_help=True,
)
console = Console()

log = logging.getLogger("finops.cli")

_DEFAULT_CONFIG = Path(__file__).parent / "config" / "settings.yaml"
_DEFAULT_SCHEMA = Path(__file__).parent / "config" / "schemas" / "config_schema.json"
_DEFAULT_RULES = Path(__file__).parent / "config" / "rules" / "anomaly_rules.yaml"
_DEFAULT_DB = Path("finops.duckdb")


@app.command()
def version() -> None:
    """Print version and exit."""
    console.print(f"finops-autopilot [bold green]{__version__}[/bold green]")


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


@app.command()
def rightsizing(
    metrics_file: Path = typer.Argument(help="JSON file with EC2/K8s/EBS metrics"),
    output: str = typer.Option("table", "--output", "-o", help="table | json"),
    db: Path = typer.Option(_DEFAULT_DB, "--db", help="DuckDB file (for savings analysis)"),
    start_date: str = typer.Option("", "--start", help="Period start for savings analysis"),
    end_date: str = typer.Option("", "--end", help="Period end for savings analysis"),
) -> None:
    """Generate EC2, K8s, storage, and savings plan recommendations from metrics JSON."""
    from finops.recommendations.ec2_rightsizer import analyze_ec2_instances
    from finops.recommendations.k8s_rightsizer import analyze_k8s_pods
    from finops.recommendations.storage_optimizer import analyze_ebs_volumes, analyze_s3_buckets
    from finops.recommendations.savings_analyzer import analyze_savings_opportunities
    from finops.ingestion.local_store import LocalStore

    data = json.loads(metrics_file.read_text(encoding="utf-8"))

    ec2_recs = analyze_ec2_instances(data.get("ec2_instances", []))
    k8s_recs = analyze_k8s_pods(data.get("kubernetes_pods", []))
    ebs_recs = analyze_ebs_volumes(data.get("ebs_volumes", []))
    s3_recs = analyze_s3_buckets(data.get("s3_buckets", []))

    savings_recs = []
    if start_date and end_date:
        with LocalStore(db) as store:
            savings_recs = analyze_savings_opportunities(store, start_date, end_date)

    total_savings = (
        sum(r.estimated_savings_usd for r in ec2_recs)
        + sum(r.estimated_savings_usd for r in ebs_recs)
        + sum(r.estimated_savings_usd for r in s3_recs)
        + sum(r.estimated_monthly_savings_usd for r in savings_recs)
    )

    if output == "json":
        console.print(json.dumps({
            "ec2": [r.as_dict() for r in ec2_recs],
            "kubernetes": [r.as_dict() for r in k8s_recs],
            "ebs": [r.as_dict() for r in ebs_recs],
            "s3": [r.as_dict() for r in s3_recs],
            "savings_plans": [r.as_dict() for r in savings_recs],
            "total_estimated_savings_usd": round(total_savings, 2),
        }, indent=2))
        return

    console.print(f"\n[bold]Total estimated monthly savings:[/bold] [green]${total_savings:.2f}[/green]\n")

    if ec2_recs:
        table = Table(title=f"EC2 Rightsizing ({len(ec2_recs)} recommendations)", header_style="bold red")
        table.add_column("Instance ID")
        table.add_column("Type")
        table.add_column("Action")
        table.add_column("Recommended")
        table.add_column("Savings/mo", justify="right")
        table.add_column("Confidence")
        for r in ec2_recs:
            table.add_row(
                r.instance_id, r.instance_type, r.action,
                r.recommended_type or "stop/terminate",
                f"${r.estimated_savings_usd:.2f}", r.confidence,
            )
        console.print(table)

    if k8s_recs:
        table = Table(title=f"K8s Rightsizing ({len(k8s_recs)} recommendations)", header_style="bold yellow")
        table.add_column("Pod")
        table.add_column("Resource")
        table.add_column("Current")
        table.add_column("Recommended")
        table.add_column("Savings %", justify="right")
        for r in k8s_recs:
            table.add_row(
                f"{r.namespace}/{r.pod_name}", r.resource,
                r.current_request, r.recommended_request,
                f"{r.estimated_savings_pct:.1f}%",
            )
        console.print(table)

    if ebs_recs or s3_recs:
        table = Table(title=f"Storage Optimization ({len(ebs_recs)+len(s3_recs)} items)", header_style="bold cyan")
        table.add_column("Resource ID")
        table.add_column("Type")
        table.add_column("Action")
        table.add_column("Savings/mo", justify="right")
        for r in [*ebs_recs, *s3_recs]:
            table.add_row(r.resource_id, r.resource_type, r.action, f"${r.estimated_savings_usd:.2f}")
        console.print(table)

    if savings_recs:
        table = Table(title=f"Savings Plans ({len(savings_recs)} opportunities)", header_style="bold green")
        table.add_column("Service")
        table.add_column("Term + Payment")
        table.add_column("Monthly cost")
        table.add_column("Savings/mo", justify="right")
        table.add_column("Discount", justify="right")
        for r in savings_recs:
            table.add_row(
                r.service, f"{r.term} {r.payment_option.replace('_', ' ')}",
                f"${r.avg_daily_cost_usd * 30:.2f}",
                f"${r.estimated_monthly_savings_usd:.2f}",
                f"{r.discount_rate_pct * 100:.0f}%",
            )
        console.print(table)


@app.command()
def report(
    db: Path = typer.Option(_DEFAULT_DB, "--db"),
    start_date: str = typer.Argument(help="Start date (YYYY-MM-DD)"),
    end_date: str = typer.Argument(help="End date (YYYY-MM-DD)"),
    metrics_file: Path = typer.Option(None, "--metrics", help="JSON metrics file for rightsizing"),
    output_dir: Path = typer.Option(Path("output/reports"), "--output-dir"),
    output_fmt: str = typer.Option("both", "--format", help="json | markdown | both"),
    account_id: str = typer.Option("", "--account-id"),
) -> None:
    """Generate a full FinOps report (anomalies + unit economics + recommendations)."""
    from finops.ingestion.local_store import LocalStore
    from finops.analysis.anomaly_detector import detect_anomalies
    from finops.analysis.unit_economics import compute_unit_economics
    from finops.analysis.top_movers import compute_top_movers
    from finops.recommendations.ec2_rightsizer import analyze_ec2_instances
    from finops.recommendations.storage_optimizer import analyze_ebs_volumes, analyze_s3_buckets
    from finops.reports.json_reporter import generate_json_report, write_json_report
    from finops.reports.markdown_reporter import generate_markdown_report, write_markdown_report

    with LocalStore(db) as store:
        anomalies_list = detect_anomalies(store, end_date=end_date)
        ue = compute_unit_economics(store, start_date, end_date)
        movers = compute_top_movers(store, start_date, end_date)  # fixed: was end_date, end_date
        acct_rows = store.query("SELECT account_id FROM cur WHERE account_id != '' LIMIT 1")
        acct = account_id or (acct_rows[0]["account_id"] if acct_rows else "unknown")

    ec2_recs, ebs_recs, s3_recs = [], [], []
    if metrics_file and metrics_file.exists():
        data = json.loads(metrics_file.read_text(encoding="utf-8"))
        ec2_recs = analyze_ec2_instances(data.get("ec2_instances", []))
        ebs_recs = analyze_ebs_volumes(data.get("ebs_volumes", []))
        s3_recs = analyze_s3_buckets(data.get("s3_buckets", []))

    storage_recs = [*ebs_recs, *s3_recs]
    total_cost = ue.total_cost

    console.print(f"[bold]Account:[/bold] {acct} | [bold]Period:[/bold] {start_date} → {end_date}")
    console.print(f"  Anomalies: [red]{len(anomalies_list)}[/red] | "
                  f"EC2 recs: [yellow]{len(ec2_recs)}[/yellow] | "
                  f"Storage recs: [cyan]{len(storage_recs)}[/cyan]")

    if output_fmt in ("json", "both"):
        jr = generate_json_report(acct, start_date, end_date, total_cost, anomalies_list,
                                   ec2_recs, [], storage_recs, unit_economics=ue.as_dict(),
                                   top_movers=movers)
        out = output_dir / f"finops-report-{start_date}-{end_date}.json"
        write_json_report(jr, out)
        console.print(f"  [green]✓[/green] JSON report: {out}")

    if output_fmt in ("markdown", "both"):
        md = generate_markdown_report(acct, start_date, end_date, total_cost, anomalies_list,
                                       ec2_recs, [], storage_recs, unit_economics=ue.as_dict())
        out = output_dir / f"finops-report-{start_date}-{end_date}.md"
        write_markdown_report(md, out)
        console.print(f"  [green]✓[/green] Markdown report: {out}")


@app.command()
def alert(
    db: Path = typer.Option(_DEFAULT_DB, "--db"),
    config: Path = typer.Option(_DEFAULT_CONFIG, "--config", "-c"),
    end_date: str = typer.Option("", "--date", "-d"),
    lookback: int = typer.Option(7, "--lookback", "-l"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Detect anomalies and dispatch alerts to configured channels."""
    from finops.ingestion.local_store import LocalStore
    from finops.analysis.anomaly_detector import detect_anomalies
    from finops.actions.alert_sender import dispatch_alerts
    from finops.utils.validators import load_yaml

    cfg = load_yaml(config)

    with LocalStore(db) as store:
        anomalies = detect_anomalies(store, end_date=end_date or None, lookback_days=lookback)
        acct = cfg.get("aws", {}).get("account_id", "unknown")
        min_d, max_d = store.date_range()

    console.print(f"[bold]Anomalies detected:[/bold] {len(anomalies)}")
    if not anomalies:
        console.print("[green]Nothing to alert.[/green]")
        return

    period = f"{min_d} → {max_d}"
    results = dispatch_alerts(anomalies, cfg, acct, period, dry_run=dry_run)

    for channel, success in results.items():
        status = "[green]✓[/green]" if success else "[red]✗[/red]"
        console.print(f"  {status} {channel}")


if __name__ == "__main__":
    app()
