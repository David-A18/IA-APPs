variable "name_prefix" {
  description = "Prefix for all resource names"
  type        = string
  default     = "finops-autopilot"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "cur_bucket_name" {
  description = "S3 bucket name for CUR reports"
  type        = string
}

variable "cur_s3_prefix" {
  description = "S3 prefix for CUR report files"
  type        = string
  default     = "cur/reports/"
}

variable "report_name" {
  description = "CUR report definition name"
  type        = string
  default     = "finops-cur-report"
}

variable "enable_github_oidc" {
  description = "Create IAM role for GitHub Actions OIDC authentication"
  type        = bool
  default     = false
}

variable "github_repo" {
  description = "GitHub repo in 'owner/repo' format (for OIDC trust policy)"
  type        = string
  default     = "David-A18/IA-APPs"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default = {
    Project   = "finops-autopilot"
    ManagedBy = "terraform"
  }
}
