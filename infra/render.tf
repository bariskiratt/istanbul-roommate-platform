# Render'daki backend'in AWS kimliği.
#
# Render OIDC desteklemiyor, bu yüzden burada (ve yalnızca burada) uzun
# ömürlü bir erişim anahtarı var. Etkisi bilerek dar: model klasörünü okumak
# ve tahmin rotasını çağırmak (ikincisi predict-service modülünde eklenir).
# Sızarsa saldırgan modeli indirip tahmin isteyebilir, o kadar; istek sınırı
# ve bütçe alarmı faturayı korur.
#
# Anahtar Terraform'da ÜRETİLMEZ (üretilseydi gizli kısmı state dosyasına
# yazılırdı). Kurulumda bir kez elle üretilir ve Render'a yapıştırılır:
#   aws iam create-access-key --user-name evdes-render-backend
resource "aws_iam_user" "render" {
  name = "${var.project}-render-backend"
  path = "/service/"
}

data "aws_iam_policy_document" "render_models" {
  statement {
    sid       = "ReadModels"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.models.arn}/${local.model_prefix}/*"]
  }
}

resource "aws_iam_user_policy" "render_models" {
  name   = "read-fair-price-models"
  user   = aws_iam_user.render.name
  policy = data.aws_iam_policy_document.render_models.json
}
