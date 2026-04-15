resource "aws_cur_report_definition" "this" {
  report_name = var.report_name
  time_unit   = "DAILY"
  format      = "textORcsv"
  compression = "GZIP"

  additional_schema_elements = [
    "RESOURCES",
    "SPLIT_COST_ALLOCATION_DATA",
  ]

  s3_bucket         = var.s3_bucket_id
  s3_region         = var.aws_region
  s3_prefix         = var.s3_prefix
  report_versioning = "OVERWRITE_REPORT"

  refresh_closed_reports = true
}
