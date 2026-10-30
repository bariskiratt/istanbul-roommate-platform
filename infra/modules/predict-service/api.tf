# HTTP API: POST /predict → Lambda `live`.
#
# Rota IAM yetkisi ister (AWS_IAM): imzasız ya da yetkisiz istek API
# Gateway'de 403 alır, Lambda'ya hiç ulaşmaz. Çağırabilen tek kimlik Render'daki
# backend'in IAM kullanıcısı (aşağıda). Paylaşılan bir gizli başlık yok.

resource "aws_apigatewayv2_api" "this" {
  name          = "${var.function_name}-api"
  protocol_type = "HTTP"
  description   = "Evdes adil kira tahmini"
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_alias.live.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 10000
}

resource "aws_apigatewayv2_route" "predict" {
  api_id             = aws_apigatewayv2_api.this.id
  route_key          = "POST /predict"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "AWS_IAM"
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/apigateway/${var.function_name}-api"
  retention_in_days = var.log_retention_days
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.this.id
  name        = "$default"
  auto_deploy = true

  # Faturanın tabanı: sınırı aşan istek 429 alır ve Lambda çalışmaz.
  default_route_settings {
    throttling_rate_limit  = var.api_rate_limit
    throttling_burst_limit = var.api_burst_limit
  }

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api.arn
    format = jsonencode({
      requestId          = "$context.requestId"
      requestTime        = "$context.requestTime"
      routeKey           = "$context.routeKey"
      status             = "$context.status"
      caller             = "$context.identity.userArn"
      responseLatency    = "$context.responseLatency"
      integrationLatency = "$context.integrationLatency"
      integrationStatus  = "$context.integrationStatus"
      error              = "$context.error.message"
    })
  }
}

resource "aws_lambda_permission" "api" {
  statement_id  = "AllowApiGatewayPredict"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  qualifier     = aws_lambda_alias.live.name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/POST/predict"
}

# Render'daki backend yalnızca bu rotayı çağırabilir.
data "aws_iam_policy_document" "render_invoke" {
  statement {
    sid       = "InvokePredict"
    actions   = ["execute-api:Invoke"]
    resources = ["${aws_apigatewayv2_api.this.execution_arn}/*/POST/predict"]
  }
}

resource "aws_iam_user_policy" "render_invoke" {
  name   = "invoke-fairprice-predict"
  user   = var.render_user_name
  policy = data.aws_iam_policy_document.render_invoke.json
}
