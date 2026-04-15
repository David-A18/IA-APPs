variable "report_name" {
  description = "Name for the CUR report definition"
  type        = string
  default     = "finops-cur-report"
}

variable "s3_bucket_id" {
  description = "ID (name) of the S3 bucket receiving CUR files"
  type        = string
}

variable "s3_prefix" {
  description = "S3 key prefix for report files"
  type        = string
  default     = "cur/reports/"
}

variable "aws_region" {
  description = "AWS region where the S3 bucket is located"
  type        = string
  default     = "us-east-1"
}
