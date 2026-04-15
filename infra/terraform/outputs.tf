output "cur_bucket_name" {
  description = "S3 bucket name for CUR reports"
  value       = module.cur_storage.bucket_id
}

output "cur_bucket_arn" {
  description = "S3 bucket ARN"
  value       = module.cur_storage.bucket_arn
}

output "cur_report_name" {
  description = "CUR report definition name"
  value       = module.cur_report.report_name
}

output "athena_workgroup_name" {
  description = "Athena workgroup name"
  value       = module.athena.workgroup_name
}

output "athena_workgroup_arn" {
  description = "Athena workgroup ARN"
  value       = module.athena.workgroup_arn
}

output "github_actions_role_arn" {
  description = "IAM role ARN for GitHub Actions OIDC (null if not enabled)"
  value       = module.iam_oidc.role_arn
}
