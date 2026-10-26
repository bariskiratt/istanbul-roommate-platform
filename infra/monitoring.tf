# Harcama ve alarm bildirimleri. Lambda/API Gateway alarmları ve CloudWatch
# panosu predict-service modülünde; hepsi aynı konuya (SNS) yazar.

resource "aws_sns_topic" "alerts" {
  name = "${var.project}-alerts"
}

# AWS ilk apply'dan sonra bu adrese bir onay e-postası yollar; bağlantıya
# tıklanana kadar alarm e-postası gelmez.
resource "aws_sns_topic_subscription" "alerts_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_budgets_budget" "monthly" {
  name         = "${var.project}-monthly"
  budget_type  = "COST"
  limit_amount = format("%.1f", var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
  }
}
