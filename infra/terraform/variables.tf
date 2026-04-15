variable "project" {
  description = "Project name — used as part of all resource names"
  type        = string
  default     = "finops-autopilot"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "cur_bucket_name" {
  description = "S3 bucket name that will store CUR reports"
  type        = string
}

variable "cur_s3_prefix" {
  description = "S3 key prefix for CUR report files"
  type        = string
  default     = "cur/reports/"
}

variable "report_name" {
  description = "Name for the CUR report definition"
  type        = string
  default     = "finops-cur-report"
}

variable "enable_github_oidc" {
  description = "Create the IAM OIDC role for GitHub Actions CI"
  type        = bool
  default     = false
}

variable "github_repo" {
  description = "GitHub repository in 'owner/repo' format (used in OIDC trust policy)"
  type        = string
  default     = "David-A18/IA-APPs"
}

variable "tags" {
  description = "Additional tags merged with common_tags on all resources"
  type        = map(string)
  default     = {}
}
