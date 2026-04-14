# FinOps Autopilot

AWS cost anomaly detection and rightsizing automation. Ingests CUR data, detects anomalies via configurable rules, generates rightsizing recommendations, and creates PRs with Terraform fixes.

## What it does

- **Ingest** — Parse AWS Cost and Usage Reports (CUR) from local CSV or S3
- **Detect** — Rule-based anomaly detection (daily spikes, new services, region outliers)
- **Recommend** — EC2 + K8s rightsizing from CloudWatch/Prometheus metrics
- **Act** — Generate GitHub PRs with Terraform fixes; send Slack alerts

## Quick start

```bash
# Install
pip install -e ".[dev]"

# Validate config
finops validate-config

# Ingest local CUR file
finops ingest tests/fixtures/sample_cur.csv --db finops.duckdb

# Ingest from S3
finops ingest s3://my-cur-bucket/cur/reports/my-report.csv

# Version
finops version
```

## Configuration

Edit `finops/config/settings.yaml` — set your AWS account ID, S3 bucket, and alert targets.

```yaml
aws:
  account_id: "123456789012"
  region: "us-east-1"
  cur:
    s3_bucket: "my-cur-bucket"
```

Rules are in `finops/config/rules/`:
- `anomaly_rules.yaml` — cost spike detection rules
- `rightsizing_rules.yaml` — EC2/K8s/storage rightsizing thresholds

## Project structure

```
finops/
├── cli.py                   # Typer CLI entrypoint
├── config/                  # settings.yaml + JSON Schema + rules
├── ingestion/               # CUR parser, enricher, DuckDB store
├── analysis/                # Anomaly detector, top movers, unit economics
├── recommendations/         # EC2, K8s, storage rightsizing
├── actions/                 # PR generator, alert sender, savings tracker
├── reports/                 # JSON + Markdown reporters + Jinja2 templates
└── utils/                   # boto3 wrapper, validators
tests/                       # pytest tests + fixtures
infra/terraform/modules/finops/  # CUR bucket, Athena workgroup
```

## Development

```bash
# Run tests
pytest

# Lint + format
ruff check finops/ tests/
ruff format finops/ tests/
```

## Roadmap

| Week | Deliverable |
|------|-------------|
| 1 | Config system + CUR ingestion (current) |
| 2 | DuckDB queries + unit economics |
| 3 | Anomaly detection + top movers |
| 4 | EC2 + K8s rightsizing |
| 5 | Reports + alerts + PR generator |
| 6 | CLI polish + Terraform module + docs |

## License

See [License.md](License.md).
