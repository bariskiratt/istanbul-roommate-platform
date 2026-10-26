# Alarmlar ve CloudWatch panosu. CV'deki sayılar (istek, p95 gecikme, soğuk
# başlangıç) bu panodan okunur (docs/AWS.md, "Ölçüm").

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${var.function_name}-errors"
  alarm_description   = "Lambda işlenmemiş hata ya da zaman aşımı verdi (backend yerel modele düşüyor)."
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = var.function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [var.alarm_topic_arn]
  ok_actions          = [var.alarm_topic_arn]
}

resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "${var.function_name}-api-5xx"
  alarm_description   = "Tahmin API'si 5 dakikada 5+ sunucu hatası döndü (ör. model yüklenemiyor: 503)."
  namespace           = "AWS/ApiGateway"
  metric_name         = "5xx"
  dimensions          = { ApiId = aws_apigatewayv2_api.this.id, Stage = "$default" }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 5
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [var.alarm_topic_arn]
  ok_actions          = [var.alarm_topic_arn]
}

locals {
  lambda_log_group = aws_cloudwatch_log_group.lambda.name
  api              = aws_apigatewayv2_api.this.id
}

resource "aws_cloudwatch_dashboard" "this" {
  dashboard_name = var.function_name

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "log", x = 0, y = 0, width = 24, height = 6
        properties = {
          title  = "Gerçek tahminler (ısıtma hariç): istek, ilan ve süre"
          region = var.region
          view   = "table"
          query  = <<-EOT
            SOURCE '${local.lambda_log_group}'
            | filter event = "predict"
            | stats count(*) as requests, sum(rows) as predictions, pct(ms, 50) as p50_ms, pct(ms, 95) as p95_ms by bin(1d)
            | sort bin(1d) desc
          EOT
        }
      },
      {
        type = "log", x = 0, y = 6, width = 12, height = 6
        properties = {
          title  = "Soğuk başlangıç (Init Duration)"
          region = var.region
          view   = "table"
          query  = <<-EOT
            SOURCE '${local.lambda_log_group}'
            | filter @type = "REPORT" and ispresent(@initDuration)
            | stats count(*) as cold_starts, pct(@initDuration, 50) as init_p50_ms, pct(@initDuration, 95) as init_p95_ms by bin(1d)
            | sort bin(1d) desc
          EOT
        }
      },
      {
        type = "metric", x = 12, y = 6, width = 12, height = 6
        properties = {
          title  = "API: uçtan uca gecikme (ms)"
          region = var.region
          view   = "timeSeries"
          period = 300
          metrics = [
            ["AWS/ApiGateway", "Latency", "ApiId", local.api, "Stage", "$default", { stat = "p50", label = "p50" }],
            ["...", { stat = "p95", label = "p95" }],
            [".", "IntegrationLatency", ".", ".", ".", ".", { stat = "p95", label = "Lambda p95" }],
          ]
        }
      },
      {
        type = "metric", x = 0, y = 12, width = 12, height = 6
        properties = {
          title   = "API: istek ve hata"
          region  = var.region
          view    = "timeSeries"
          stacked = false
          period  = 300
          metrics = [
            ["AWS/ApiGateway", "Count", "ApiId", local.api, "Stage", "$default", { stat = "Sum" }],
            [".", "4xx", ".", ".", ".", ".", { stat = "Sum" }],
            [".", "5xx", ".", ".", ".", ".", { stat = "Sum" }],
          ]
        }
      },
      {
        type = "metric", x = 12, y = 12, width = 12, height = 6
        properties = {
          title  = "Lambda: çağrı (ısıtma dahil), hata, kısıtlama"
          region = var.region
          view   = "timeSeries"
          period = 300
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", var.function_name, { stat = "Sum" }],
            [".", "Errors", ".", ".", { stat = "Sum" }],
            [".", "Throttles", ".", ".", { stat = "Sum" }],
          ]
        }
      },
    ]
  })
}
