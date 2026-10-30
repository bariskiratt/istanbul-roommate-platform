output "github_role_arn" {
  description = "github_oidc = true ise: GitHub → Settings → Secrets and variables → Actions → Variables → AWS_ROLE_ARN"
  value       = var.github_oidc ? aws_iam_role.github_deploy[0].arn : null
}

output "github_user" {
  description = "github_oidc = false ise GitHub'ın anahtarı bu kullanıcı için üretilir: aws iam create-access-key --user-name <bu>"
  value       = var.github_oidc ? null : aws_iam_user.github_deploy[0].name
}

output "model_bucket" {
  description = "Render → Environment → FAIRPRICE_MODEL_BUCKET"
  value       = aws_s3_bucket.models.bucket
}

output "render_user" {
  description = "Render'ın anahtarı bu kullanıcı için üretilir: aws iam create-access-key --user-name <bu>"
  value       = aws_iam_user.render.name
}

output "ecr_repository_url" {
  value = aws_ecr_repository.fairprice.repository_url
}

output "lambda_function" {
  value = local.function_name
}

output "predict_url" {
  description = "Render → Environment → FAIRPRICE_URL (enable_predict_service = true olunca dolar)"
  value       = var.enable_predict_service ? module.predict_service[0].predict_url : null
}

output "dashboard_url" {
  value = var.enable_predict_service ? module.predict_service[0].dashboard_url : null
}
