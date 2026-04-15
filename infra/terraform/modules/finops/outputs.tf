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

output "github_actions_role_arn" {
  description = "IAM role ARN for GitHub Actions OIDC (set enable_github_oidc=true to create)"
  value       = var.enable_github_oidc ? aws_iam_role.finops_ci[0].arn : null
}
