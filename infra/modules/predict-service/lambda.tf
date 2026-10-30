# --- Lambda'nın kendi kimliği: modeli okur, kendi log grubuna yazar. ----------

data "aws_iam_policy_document" "lambda_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${var.function_name}-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

data "aws_iam_policy_document" "lambda" {
  statement {
    sid       = "ReadModels"
    actions   = ["s3:GetObject"]
    resources = ["${var.model_bucket_arn}/${var.model_prefix}/*"]
  }

  # AWSLambdaBasicExecutionRole her log grubuna yazar; bu yalnızca kendisininkine.
  statement {
    sid       = "WriteOwnLogs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.lambda.arn}:*"]
  }
}

resource "aws_iam_role_policy" "lambda" {
  name   = "fairprice-runtime"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda.json
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = var.log_retention_days
}

# --- Fonksiyon, sürümler ve `live` takma adı ---------------------------------
#
# Terraform fonksiyonu kurar ve ilk sürümü yayınlar. Sonraki imajları GitHub
# Actions dağıtır: yeni sürüm yayınlar, duman testinden geçerse `live`ı ona
# çevirir (.github/workflows/aws-deploy.yml). Bu yüzden Terraform imaja ve
# takma adın gösterdiği sürüme bir daha dokunmaz (ignore_changes).
#
# Dikkat: yayınlanmış bir sürüm yapılandırmasıyla birlikte dondurulur. Bellek
# gibi bir ayarı burada değiştirip apply ettikten sonra "AWS yayını" iş akışını
# elle çalıştır; değişiklik ancak yeni sürümle `live`a geçer.

resource "aws_lambda_function" "this" {
  function_name = var.function_name
  description   = "Evdes adil kira bandı (LightGBM q25/q50/q75)"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = var.image_uri
  architectures = ["x86_64"]
  memory_size   = var.memory_mb
  # Yeni bir imajın ilk soğuk başlangıcı (Lambda imajı henüz önbelleğe
  # almamışken pandas/LightGBM importu) 10 sn'yi aşabiliyor: ilk kurulumda
  # init 10 sn'de kesildi, ancak üçüncü denemede açıldı. Init 10 sn'yi aşınca
  # Lambda onu bu süre içinde yeniden dener, bu yüzden pay bırakıyoruz.
  # Kullanıcıyı etkilemez: backend 3 sn'den sonra yerel modelle cevap verir.
  timeout = 30
  publish = true

  reserved_concurrent_executions = var.reserved_concurrency

  environment {
    variables = {
      MODEL_BUCKET = var.model_bucket_name
    }
  }

  depends_on = [aws_cloudwatch_log_group.lambda, aws_iam_role_policy.lambda]

  lifecycle {
    ignore_changes = [image_uri]
  }
}

resource "aws_lambda_alias" "live" {
  name             = "live"
  description      = "API Gateway ve ısıtıcının çağırdığı sürüm; dağıtım iş akışı yönetir"
  function_name    = aws_lambda_function.this.function_name
  function_version = aws_lambda_function.this.version

  lifecycle {
    ignore_changes = [function_version]
  }
}

# --- Isıtıcı: az trafikte bir ortam hep sıcak kalsın ------------------------

resource "aws_cloudwatch_event_rule" "warmer" {
  count               = var.warmer_enabled ? 1 : 0
  name                = "${var.function_name}-warmer"
  description         = "Lambda'yı 5 dakikada bir ısıtır (handler.py: warmup)"
  schedule_expression = "rate(5 minutes)"
}

resource "aws_cloudwatch_event_target" "warmer" {
  count = var.warmer_enabled ? 1 : 0
  rule  = aws_cloudwatch_event_rule.warmer[0].name
  arn   = aws_lambda_alias.live.arn
  input = jsonencode({ warmup = true })
}

resource "aws_lambda_permission" "warmer" {
  count         = var.warmer_enabled ? 1 : 0
  statement_id  = "AllowEventBridgeWarmer"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  qualifier     = aws_lambda_alias.live.name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.warmer[0].arn
}
