variable "bucket_name" {
  description = "Name of the S3 bucket for CUR reports"
  type        = string
}

variable "cur_prefix" {
  description = "S3 key prefix for CUR files (used in lifecycle rule filter)"
  type        = string
  default     = "cur/reports/"
}

variable "tags" {
  description = "Tags to apply to all resources in this module"
  type        = map(string)
  default     = {}
}
