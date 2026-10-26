output "predict_url" {
  value = "${aws_apigatewayv2_api.this.api_endpoint}/predict"
}

output "function_arn" {
  value = aws_lambda_function.this.arn
}

output "dashboard_url" {
  value = "https://${var.region}.console.aws.amazon.com/cloudwatch/home?region=${var.region}#dashboards/dashboard/${aws_cloudwatch_dashboard.this.dashboard_name}"
}
