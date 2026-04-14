# FinOps Autopilot

**Stop watching dashboards. Start automating savings.**

FinOps Autopilot is an open-core CLI tool that ingests AWS Cost and Usage Reports, detects spending anomalies, generates rightsizing recommendations for EC2 and Kubernetes, and opens pull requests with ready-to-apply Terraform fixes — so your cloud bill goes down without manual spreadsheet work.

---

## Why this exists

Most teams have cost dashboards. Very few have cost **automation**. The gap between "we can see the waste" and "we fixed the waste" is where money burns. FinOps Autopilot closes that gap:

| Problem | How Autopilot solves it |
|---------|------------------------|
| CUR data is massive and hard to query | Parses, normalizes, and stores it in DuckDB for instant SQL |
| Anomalies go unnoticed for days | Rule-based detection with configurable thresholds + Slack alerts |
| Rightsizing is manual and slow | Automated recommendations based on CloudWatch/Prometheus metrics |
| Recommendations sit in tickets forever | Generates PRs with Terraform changes, ready for human approval |
| Cost allocation is broken | Tag-based enrichment with service categories, teams, and environments |

---

## Features

### Ingest
- Parse AWS CUR files from **local CSV** or **S3**
- Normalize 16+ CUR column types into clean, queryable fields
- Enrich with service categories (Compute, Storage, Database, Networking...)
- Store in **DuckDB** (local dev) or query via **Athena** (production)

### Detect
- Rule-based anomaly detection (YAML-configurable)
- Daily cost spikes, service cost spikes, new service detection
- Top movers — biggest absolute and percentage changes
- Configurable lookback windows and minimum thresholds

### Recommend
- **EC2 rightsizing** — CPU/memory utilization from CloudWatch
- **K8s rightsizing** — requests vs actual usage from Prometheus
- **Storage optimization** — S3 lifecycle tiers, EBS gp2→gp3 migration
- **Savings Plans analysis** — identify stable workloads for commitments

### Act
- Generate **GitHub PRs** with Terraform changes
- Human approval required before applying
- **Slack/email alerts** for anomalies and recommendations
- Track verified savings over time

---

## Quick start

### Prerequisites

- Python 3.12+
- AWS credentials configured (for S3/CloudWatch access)
- Git

### Install

```bash
git clone https://github.com/David-A18/IA-APPs.git
cd IA-APPs
pip install -e ".[dev]"
```

### First run

```bash
# Validate your configuration
finops validate-config

# Ingest a local CUR file
finops ingest tests/fixtures/sample_cur.csv --db finops.duckdb

# Ingest from S3
finops ingest s3://your-cur-bucket/cur/reports/report.csv

# Check version
finops version
```

---

## Configuration

All configuration lives in `finops/config/` as human-readable YAML, validated against JSON Schema.

### Main settings — `finops/config/settings.yaml`

```yaml
aws:
  account_id: "123456789012"
  region: "us-east-1"
  cur:
    s3_bucket: "my-cur-bucket"
    s3_prefix: "cur/reports/"

anomaly_detection:
  thresholds:
    daily_cost_spike_pct: 20
    service_cost_spike_pct: 50
    absolute_min_delta_usd: 10.0
  lookback_days: 7

alerts:
  slack:
    enabled: true
    webhook_url: "https://hooks.slack.com/services/..."
    channel: "#finops-alerts"
```

### Detection rules — `finops/config/rules/`

| File | Controls |
|------|----------|
| `anomaly_rules.yaml` | Cost spike thresholds, lookback windows, severity levels |
| `rightsizing_rules.yaml` | CPU/memory/storage utilization thresholds for recommendations |

---

## Project structure

```
finops/
├── cli.py                        # Typer CLI — main entrypoint
├── config/
│   ├── settings.yaml             # Global config (AWS, thresholds, alerts)
│   ├── rules/
│   │   ├── anomaly_rules.yaml    # Anomaly detection rules
│   │   └── rightsizing_rules.yaml# Rightsizing thresholds
│   └── schemas/
│       └── config_schema.json    # JSON Schema for validation
├── ingestion/
│   ├── cur_parser.py             # Parse CUR CSV (local + S3)
│   ├── cur_enricher.py           # Tag-based cost allocation
│   └── local_store.py            # DuckDB wrapper + SQL queries
├── analysis/
│   ├── anomaly_detector.py       # Rule engine + statistical detection
│   ├── top_movers.py             # Biggest cost changes
│   └── unit_economics.py         # Cost per business unit
├── recommendations/
│   ├── ec2_rightsizer.py         # EC2 instance recommendations
│   ├── k8s_rightsizer.py         # K8s requests/limits tuning
│   ├── storage_optimizer.py      # S3/EBS optimization
│   └── savings_analyzer.py       # RI/SP analysis
├── actions/
│   ├── pr_generator.py           # GitHub PR creation with Terraform changes
│   ├── alert_sender.py           # Slack/email/webhook notifications
│   └── savings_tracker.py        # Track verified savings
├── reports/
│   ├── json_reporter.py          # Structured JSON output
│   ├── markdown_reporter.py      # Human-readable reports
│   └── templates/                # Jinja2 templates
└── utils/
    ├── aws_client.py             # Thin boto3 wrapper (STS, S3, CW, CE)
    └── validators.py             # YAML + JSON Schema validation
tests/                            # pytest suite + CUR fixtures
infra/terraform/modules/finops/   # S3 bucket, CUR report, Athena workgroup
```

---

## Development

### Run tests

```bash
pytest
```

### Lint and format

```bash
ruff check finops/ tests/
ruff format finops/ tests/
```

### Type checking

```bash
mypy finops/
```

---

## Roadmap

| Phase | Week | Deliverable | Status |
|-------|------|-------------|--------|
| **Foundation** | 1 | Config system + CUR ingestion + DuckDB store | Done |
| **Queries** | 2 | Advanced DuckDB queries + unit economics | Next |
| **Detection** | 3 | Anomaly detection engine + top movers | Planned |
| **Optimization** | 4 | EC2 + K8s rightsizing recommendations | Planned |
| **Automation** | 5 | Reports + Slack alerts + PR generator | Planned |
| **Polish** | 6 | CLI UX + Terraform module + documentation | Planned |

---

## Tech stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Language | Python 3.12+ | AWS ecosystem, fast prototyping, rich CLI libraries |
| CLI | Typer + Rich | Modern terminal UX with colors and tables |
| Local data | DuckDB | Blazing-fast SQL on local files, zero infrastructure |
| Production data | S3 + Athena | Serverless, scales with CUR size |
| AWS access | boto3 | Standard Python SDK for AWS |
| K8s access | kubernetes-client | Standard Python SDK for Kubernetes |
| Config | YAML + JSON Schema | Human-readable, machine-validatable |
| Templates | Jinja2 | For reports and PR bodies |
| IaC | Terraform | Portable, modular, industry standard |
| Tests | pytest + moto | Fast tests with AWS service mocking |
| Linting | ruff | Replaces flake8 + black + isort in one tool |

---

## How it works

```
┌──────────────┐     ┌───────────────┐     ┌──────────────────┐
│  AWS CUR     │────▶│  Ingest +     │────▶│  DuckDB / Athena │
│  (S3/local)  │     │  Enrich       │     │  (queryable)     │
└──────────────┘     └───────────────┘     └────────┬─────────┘
                                                     │
                     ┌───────────────┐               │
                     │  Anomaly      │◀──────────────┘
                     │  Detection    │───────────┐
                     └───────────────┘           │
                                                 ▼
                     ┌───────────────┐     ┌──────────────────┐
                     │  Rightsizing   │────▶│  Reports +       │
                     │  Engine       │     │  Alerts          │
                     └───────────────┘     └────────┬─────────┘
                                                     │
                                                     ▼
                                            ┌──────────────────┐
                                            │  GitHub PRs      │
                                            │  (Terraform)     │
                                            └──────────────────┘
```

---

## Contributing

This project is under active development. See the [License](License.md) for usage terms.

If you find a bug or have a feature request, open an issue on [GitHub](https://github.com/David-A18/IA-APPs/issues).

---

## Author

**David Angarita** — Cloud/DevOps/FinOps Engineer

Building tools that turn cloud cost visibility into automated action.

---

## License

Proprietary Source-Available License. See [License.md](License.md) for full terms.
