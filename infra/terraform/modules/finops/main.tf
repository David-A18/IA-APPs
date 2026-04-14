terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# S3 bucket for Cost and Usage Reports
resource "aws_s3_bucket" "cur" {
  bucket = var.cur_bucket_name
  tags   = var.tags
}

resource "aws_s3_bucket_versioning" "cur" {
  bucket = aws_s3_bucket.cur.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "cur" {
  bucket = aws_s3_bucket.cur.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "cur" {
  bucket = aws_s3_bucket.cur.id
  rule {
    id     = "archive-old-reports"
    status = "Enabled"
    filter { prefix = "cur/" }
    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }
    transition {
      days          = 365
      storage_class = "GLACIER"
    }
  }
}

# CUR report definition
resource "aws_cur_report_definition" "main" {
  report_name                = var.report_name
  time_unit                  = "DAILY"
  format                     = "textORcsv"
  compression                = "GZIP"
  additional_schema_elements = ["RESOURCES"]
  s3_bucket                  = aws_s3_bucket.cur.id
  s3_region                  = var.aws_region
  s3_prefix                  = var.cur_s3_prefix
  report_versioning          = "OVERWRITE_REPORT"
  refresh_closed_reports     = true
}

# Athena workgroup for production queries
resource "aws_athena_workgroup" "finops" {
  name  = "${var.name_prefix}-finops"
  state = "ENABLED"
  configuration {
    result_configuration {
      output_location = "s3://${aws_s3_bucket.cur.id}/athena-results/"
      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true
    bytes_scanned_cutoff_per_query     = 10737418240 # 10 GB guard rail
  }
  tags = var.tags
}
