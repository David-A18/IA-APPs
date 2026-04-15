output "workgroup_name" {
  description = "Athena workgroup name"
  value       = aws_athena_workgroup.this.name
}

output "workgroup_arn" {
  description = "Athena workgroup ARN"
  value       = aws_athena_workgroup.this.arn
}

output "results_location" {
  description = "S3 URI where Athena stores query results"
  value       = "s3://${var.results_bucket_id}/athena-results/"
}
