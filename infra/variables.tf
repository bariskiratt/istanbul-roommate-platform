variable "region" {
  description = "Her şeyin kurulacağı bölge. Render servisi Oregon'da (us-west-2): tahmin isteği bölge dışına çıkmasın."
  type        = string
  default     = "us-west-2"
}

variable "project" {
  description = "Kaynak adlarının ön eki."
  type        = string
  default     = "evdes"
}

variable "github_repo" {
  description = "AWS'ye yalnızca bu deponun main dalındaki iş akışları girebilir (OIDC)."
  type        = string
  default     = "bariskiratt/istanbul-roommate-platform"
}

variable "alert_email" {
  description = "Bütçe ve alarm e-postalarının gideceği adres (terraform.tfvars'a yaz; depoya girmez)."
  type        = string

  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.alert_email))
    error_message = "Geçerli bir e-posta adresi olmalı."
  }
}

variable "monthly_budget_usd" {
  description = "Aylık harcama alarmı (USD). Gerçek harcama %80'i, tahmini harcama %100'ü geçince e-posta gelir."
  type        = number
  default     = 5
}

variable "enable_predict_service" {
  description = <<-EOT
    Lambda + API Gateway'i kur. İlk apply'da false kalır: Lambda'nın
    çalıştıracağı imaj ECR'de henüz yok. "AWS yayını" iş akışı imajı ECR'ye
    gönderdikten sonra true yapılıp yeniden apply edilir (docs/AWS.md, Kurulum).
  EOT
  type        = bool
  default     = false
}

variable "lambda_memory_mb" {
  description = "Lambda belleği. CPU bellekle orantılı verilir; 1024 MB'ta tek satırlık tahmin ~15 ms."
  type        = number
  default     = 1024
}

variable "lambda_reserved_concurrency" {
  description = <<-EOT
    Lambda'nın aynı anda çalışabilecek kopya sayısı üst sınırı (-1 = sınır yok).
    Yeni AWS hesaplarında hesap geneli sınır 10'dur ve AWS ayrılmamış kapasitenin
    10'un altına inmesine izin vermez; bu yüzden varsayılan -1. Kota artınca
    (Service Quotas → Lambda → Concurrent executions) ör. 5 yap. O zamana kadar
    faturayı API Gateway'deki istek sınırı korur.
  EOT
  type        = number
  default     = -1
}

variable "api_rate_limit" {
  description = "API Gateway: saniyede ortalama istek sınırı (aşan istek 429 alır, Lambda'ya ulaşmaz)."
  type        = number
  default     = 5
}

variable "api_burst_limit" {
  description = "API Gateway: anlık patlama sınırı."
  type        = number
  default     = 10
}

variable "warmer_enabled" {
  description = "EventBridge her 5 dakikada Lambda'yı ısıtsın (az trafikte soğuk başlangıcı önler; ayda ~8.600 çağrı, ücretsiz katmanda)."
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "CloudWatch log saklama süresi."
  type        = number
  default     = 30
}
