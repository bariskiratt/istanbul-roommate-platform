# Tahmin servisi: ECR deposu her zaman, Lambda + API Gateway ikinci aşamada.

locals {
  function_arn = "arn:aws:lambda:${var.region}:${local.account_id}:function:${local.function_name}"
}

resource "aws_ecr_repository" "fairprice" {
  name = local.function_name

  # Etiketler değiştirilemez: bir etiket her zaman aynı imajı gösterir.
  # Dağıtım her koşuda yeni bir etiket kullanır (aws-deploy.yml).
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true # bilinen açıklar için temel tarama (ücretsiz)
  }
}

resource "aws_ecr_lifecycle_policy" "fairprice" {
  repository = aws_ecr_repository.fairprice.name

  # Son 10 imaj kalır. Daha eski bir Lambda sürümüne geri dönülemez (imajı
  # silinmiş olur); geri dönüş zaten bir önceki sürüme yapılır.
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Son 10 imaji tut"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = { type = "expire" }
    }]
  })
}

# Lambda imajı bu depodan çeker; yetki yalnızca bu hesabın bu fonksiyonuna.
data "aws_iam_policy_document" "ecr_lambda_pull" {
  statement {
    sid     = "LambdaImagePull"
    actions = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "aws:sourceArn"
      values   = ["${local.function_arn}*"]
    }
  }
}

resource "aws_ecr_repository_policy" "fairprice" {
  repository = aws_ecr_repository.fairprice.name
  policy     = data.aws_iam_policy_document.ecr_lambda_pull.json
}

# İlk kurulumda Lambda, ECR'deki en yeni imajla doğar; sonraki imajları
# GitHub Actions dağıtır (Terraform image_uri'ye bir daha dokunmaz).
data "aws_ecr_image" "bootstrap" {
  count           = var.enable_predict_service ? 1 : 0
  repository_name = aws_ecr_repository.fairprice.name
  most_recent     = true
}

module "predict_service" {
  source = "./modules/predict-service"
  count  = var.enable_predict_service ? 1 : 0

  function_name        = local.function_name
  image_uri            = "${aws_ecr_repository.fairprice.repository_url}@${data.aws_ecr_image.bootstrap[0].image_digest}"
  memory_mb            = var.lambda_memory_mb
  reserved_concurrency = var.lambda_reserved_concurrency
  model_bucket_name    = aws_s3_bucket.models.bucket
  model_bucket_arn     = aws_s3_bucket.models.arn
  model_prefix         = local.model_prefix
  render_user_name     = aws_iam_user.render.name
  api_rate_limit       = var.api_rate_limit
  api_burst_limit      = var.api_burst_limit
  warmer_enabled       = var.warmer_enabled
  log_retention_days   = var.log_retention_days
  alarm_topic_arn      = aws_sns_topic.alerts.arn
  region               = var.region
}
