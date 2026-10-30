# GitHub Actions'ın AWS kimliği. İki yol var (var.github_oidc):
#
# OIDC (klasik hesap, github_oidc = true): saklanan anahtar YOK. İş akışı her
# koşuda GitHub'dan kısa ömürlü, imzalı bir kimlik belirteci alır; AWS onu bu
# sağlayıcıyla doğrular ve aşağıdaki rolü bir saatliğine verir. Rolü yalnızca
# bu deponun MAIN dalında koşan iş akışları üstlenebilir.
#
# IAM kullanıcısı (yeni "proje" hesapları, varsayılan): bu hesaplar OIDC
# sağlayıcısı kurmayı yasaklıyor, bu yüzden iş akışı bir erişim anahtarıyla
# girer. Anahtar GitHub'da secret olarak durur; GitHub secret'ları PR'lara
# (çatallardan gelenler dahil) verilmez ve iş akışı yalnızca main'de koşar.
# Anahtar Terraform'da ÜRETİLMEZ (gizli kısmı state dosyasına yazılırdı):
#   aws iam create-access-key --user-name evdes-github-deploy
#
# Yetkiler iki yolda da aynı: aşağıdaki github_deploy belgesi.

resource "aws_iam_openid_connect_provider" "github" {
  count          = var.github_oidc ? 1 : 0
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_policy_document" "github_trust" {
  count = var.github_oidc ? 1 : 0

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github[0].arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # workflow_run ve workflow_dispatch koşuları main'in bağlamında çalışır.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repo}:ref:refs/heads/main"]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  count                = var.github_oidc ? 1 : 0
  name                 = "${var.project}-github-deploy"
  description          = "GitHub Actions (${var.github_repo}, main): model yükleme ve Lambda dağıtımı"
  assume_role_policy   = data.aws_iam_policy_document.github_trust[0].json
  max_session_duration = 3600
}

resource "aws_iam_user" "github_deploy" {
  count = var.github_oidc ? 0 : 1
  name  = "${var.project}-github-deploy"
  path  = "/service/"
}

# En az yetki: yalnızca bu projenin kovası, ECR deposu ve Lambda fonksiyonu.
# IAM, ağ ya da başka bir kaynağı değiştiremez; altyapı değişikliği
# (terraform apply) bilerek insan elinde.
data "aws_iam_policy_document" "github_deploy" {
  # ListBucket olmadan eksik nesne 404 değil 403 döner; publish_model.py
  # "henüz model yok" ile "yetki yok"u ayırt edebilsin diye.
  statement {
    sid       = "ListModelBucket"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.models.arn]
  }

  statement {
    sid       = "ReadWriteModels"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.models.arn}/${local.model_prefix}/*"]
  }

  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"] # bu eylem kaynak düzeyinde kısıtlanamıyor
  }

  statement {
    sid = "EcrPush"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeImages",
      "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]
    resources = [aws_ecr_repository.fairprice.arn]
  }

  statement {
    sid = "LambdaDeploy"
    actions = [
      "lambda:GetAlias",
      "lambda:GetFunction",
      "lambda:GetFunctionConfiguration",
      "lambda:InvokeFunction", # yeni sürüme duman testi
      "lambda:ListVersionsByFunction",
      "lambda:PublishVersion",
      "lambda:UpdateAlias",
      "lambda:UpdateFunctionCode",
    ]
    resources = [local.function_arn, "${local.function_arn}:*"]
  }
}

resource "aws_iam_role_policy" "github_deploy" {
  count  = var.github_oidc ? 1 : 0
  name   = "deploy-fairprice"
  role   = aws_iam_role.github_deploy[0].id
  policy = data.aws_iam_policy_document.github_deploy.json
}

resource "aws_iam_user_policy" "github_deploy" {
  count  = var.github_oidc ? 0 : 1
  name   = "deploy-fairprice"
  user   = aws_iam_user.github_deploy[0].name
  policy = data.aws_iam_policy_document.github_deploy.json
}
