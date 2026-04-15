variable "name_prefix" {
  description = "Prefix for the Athena workgroup name"
  type        = string
}

variable "results_bucket_id" {
  description = "S3 bucket ID where Athena query results are stored"
  type        = string
}

variable "bytes_scanned_cutoff" {
  description = "Max bytes scanned per query before Athena kills it (cost guard rail)"
  type        = number
  default     = 10737418240 # 10 GB
}

variable "tags" {
  description = "Tags to apply to all resources in this module"
  type        = map(string)
  default     = {}
}
