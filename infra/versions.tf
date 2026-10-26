terraform {
  # 1.10+: S3 arka ucunda kilit için DynamoDB tablosu gerekmez (use_lockfile).
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Durum dosyası (state) S3'te, sürümlü ve şifreli; kilit de aynı kovada.
  # Kova adı hesap kimliğini içerdiği için burada yazmıyor, bootstrap.sh
  # `terraform init -backend-config="bucket=evdes-tfstate-<hesap-id>"` ile veriyor.
  backend "s3" {
    key          = "evdes/terraform.tfstate"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.region

  # Konsolda "bu kaynak nereden geldi?" sorusunun cevabı her kaynağın üstünde.
  default_tags {
    tags = {
      Project   = var.project
      ManagedBy = "terraform"
      Source    = "github.com/${var.github_repo}/tree/main/infra"
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id

  # Adlar GitHub Actions'taki adlarla aynı olmalı (.github/workflows/aws-deploy.yml
  # env bloğu): iş akışı yalnızca rol ARN'sini değişken olarak alır, gerisini
  # bu kuraldan türetir.
  function_name = "${var.project}-fairprice"
  model_prefix  = "fair-price"
}
