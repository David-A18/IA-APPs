resource "aws_athena_workgroup" "this" {
  name  = "${var.name_prefix}-finops"
  state = "ENABLED"

  configuration {
    result_configuration {
      output_location = "s3://${var.results_bucket_id}/athena-results/"

      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }

    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true

    bytes_scanned_cutoff_per_query = var.bytes_scanned_cutoff
  }

  tags = var.tags
}
