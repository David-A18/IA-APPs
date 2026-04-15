output "role_arn" {
  description = "IAM role ARN for GitHub Actions (null when enabled=false)"
  value       = var.enabled ? aws_iam_role.this[0].arn : null
}

output "role_name" {
  description = "IAM role name (null when enabled=false)"
  value       = var.enabled ? aws_iam_role.this[0].name : null
}
