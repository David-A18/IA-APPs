# Remote state backend — S3 + DynamoDB locking.
# Uncomment and fill in values before running `terraform init`.
#
# Pre-requisites (create once manually or via bootstrap script):
#   aws s3api create-bucket --bucket <tfstate-bucket> --region us-east-1
#   aws dynamodb create-table --table-name terraform-locks \
#     --attribute-definitions AttributeName=LockID,AttributeType=S \
#     --key-schema AttributeName=LockID,KeyType=HASH \
#     --billing-mode PAY_PER_REQUEST
#
# terraform {
#   backend "s3" {
#     bucket         = "my-company-terraform-state"
#     key            = "finops-autopilot/terraform.tfstate"
#     region         = "us-east-1"
#     encrypt        = true
#     dynamodb_table = "terraform-locks"
#   }
# }
