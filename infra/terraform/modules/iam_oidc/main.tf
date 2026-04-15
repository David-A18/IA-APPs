data "aws_iam_openid_connect_provider" "github" {
  count = var.enabled ? 1 : 0
  url   = "https://token.actions.githubusercontent.com"
}

resource "aws_iam_role" "this" {
  count = var.enabled ? 1 : 0
  name  = "${var.name_prefix}-github-actions"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = data.aws_iam_openid_connect_provider.github[0].arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        StringLike = {
          "token.actions.githubusercontent.com:sub" = "repo:${var.github_repo}:*"
        }
      }
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "s3_read" {
  count = var.enabled ? 1 : 0
  name  = "s3-cur-read"
  role  = aws_iam_role.this[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CURBucketRead"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:ListBucket"]
        Resource = [
          var.cur_bucket_arn,
          "${var.cur_bucket_arn}/*",
        ]
      },
      {
        Sid    = "AthenaResultsWrite"
        Effect = "Allow"
        Action = ["s3:PutObject", "s3:GetObject"]
        Resource = "${var.cur_bucket_arn}/athena-results/*"
      },
    ]
  })
}

resource "aws_iam_role_policy" "athena_query" {
  count = var.enabled ? 1 : 0
  name  = "athena-query"
  role  = aws_iam_role.this[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "AthenaWorkgroup"
      Effect = "Allow"
      Action = [
        "athena:StartQueryExecution",
        "athena:GetQueryExecution",
        "athena:GetQueryResults",
        "athena:StopQueryExecution",
      ]
      Resource = var.athena_workgroup
    }]
  })
}

resource "aws_iam_role_policy" "observability" {
  count = var.enabled ? 1 : 0
  name  = "observability-read"
  role  = aws_iam_role.this[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchMetricsRead"
        Effect = "Allow"
        Action = [
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:ListMetrics",
          "cloudwatch:GetMetricData",
        ]
        Resource = "*"
      },
      {
        Sid      = "CostExplorerRead"
        Effect   = "Allow"
        Action   = ["ce:GetCostAndUsage", "ce:GetRightsizingRecommendation"]
        Resource = "*"
      },
    ]
  })
}
