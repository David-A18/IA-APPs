output "cur_bucket_name" {
  description = "S3 bucket name storing CUR reports"
  value       = aws_s3_bucket.cur.id
}

output "cur_bucket_arn" {
  description = "S3 bucket ARN"
  value       = aws_s3_bucket.cur.arn
}

output "athena_workgroup_name" {
  description = "Athena workgroup name for FinOps queries"
  value       = aws_athena_workgroup.finops.name
}

output "report_name" {
  description = "CUR report definition name"
  value       = aws_cur_report_definition.main.report_name
}
