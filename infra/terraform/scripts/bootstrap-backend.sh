#!/usr/bin/env bash
# Bootstrap the S3 bucket and DynamoDB table needed for Terraform remote state.
# Run once per AWS account before terraform init.
# Usage: ./scripts/bootstrap-backend.sh <bucket-name> [region]

set -euo pipefail

BUCKET="${1:?Usage: $0 <bucket-name> [region]}"
REGION="${2:-us-east-1}"
TABLE="terraform-locks"

echo "Creating S3 state bucket: $BUCKET ($REGION)"
if [[ "$REGION" == "us-east-1" ]]; then
  aws s3api create-bucket \
    --bucket "$BUCKET" \
    --region "$REGION"
else
  aws s3api create-bucket \
    --bucket "$BUCKET" \
    --region "$REGION" \
    --create-bucket-configuration LocationConstraint="$REGION"
fi

echo "Enabling versioning on $BUCKET"
aws s3api put-bucket-versioning \
  --bucket "$BUCKET" \
  --versioning-configuration Status=Enabled

echo "Enabling SSE on $BUCKET"
aws s3api put-bucket-encryption \
  --bucket "$BUCKET" \
  --server-side-encryption-configuration '{
    "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
  }'

echo "Blocking public access on $BUCKET"
aws s3api put-public-access-block \
  --bucket "$BUCKET" \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

echo "Creating DynamoDB lock table: $TABLE"
aws dynamodb create-table \
  --table-name "$TABLE" \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region "$REGION" 2>/dev/null || echo "Table $TABLE already exists — skipping."

echo ""
echo "Done. Add this to infra/terraform/backend.tf:"
echo ""
echo '  terraform {'
echo '    backend "s3" {'
echo "      bucket         = \"$BUCKET\""
echo '      key            = "finops-autopilot/terraform.tfstate"'
echo "      region         = \"$REGION\""
echo '      encrypt        = true'
echo "      dynamodb_table = \"$TABLE\""
echo '    }'
echo '  }'
