variable "enabled" {
  description = "Set to true to create the OIDC role. False = no resources created."
  type        = bool
  default     = false
}

variable "name_prefix" {
  description = "Prefix for the IAM role name"
  type        = string
}

variable "github_repo" {
  description = "GitHub repo in 'owner/repo' format used in the OIDC trust condition"
  type        = string
}

variable "cur_bucket_arn" {
  description = "ARN of the CUR S3 bucket (used in S3 policy)"
  type        = string
}

variable "athena_workgroup" {
  description = "ARN of the Athena workgroup (used in Athena policy)"
  type        = string
}

variable "tags" {
  description = "Tags applied to the IAM role"
  type        = map(string)
  default     = {}
}
