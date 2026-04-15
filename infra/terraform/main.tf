terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ── Module calls ──────────────────────────────────────────────────────────────

module "cur_storage" {
  source = "./modules/cur_storage"

  bucket_name = var.cur_bucket_name
  cur_prefix  = var.cur_s3_prefix
  tags        = local.common_tags
}

module "cur_report" {
  source = "./modules/cur_report"

  report_name  = var.report_name
  s3_bucket_id = module.cur_storage.bucket_id
  s3_prefix    = var.cur_s3_prefix
  aws_region   = var.aws_region
}

module "athena" {
  source = "./modules/athena"

  name_prefix        = local.name_prefix
  results_bucket_id  = module.cur_storage.bucket_id
  tags               = local.common_tags
}

module "iam_oidc" {
  source = "./modules/iam_oidc"

  enabled          = var.enable_github_oidc
  name_prefix      = local.name_prefix
  github_repo      = var.github_repo
  cur_bucket_arn   = module.cur_storage.bucket_arn
  athena_workgroup = module.athena.workgroup_arn
  tags             = local.common_tags
}
