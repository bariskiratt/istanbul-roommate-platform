#!/usr/bin/env bash
# Terraform'un durum (state) kovasını kurar ve `terraform init` yapar.
#
# Bir kez, AWS CLI'da kendi kullanıcınla oturum açtıktan sonra çalıştır
# (`aws sso login` ya da `aws configure`). Tekrar çalıştırmak zararsız:
# kova varsa dokunmaz, yalnızca init yapar. Ayrıntı: docs/AWS.md.
#
# Durum kovası Terraform'un DIŞINDA kurulur, çünkü Terraform durumunu
# yazacağı kovayı kendisi kuramaz (tavuk-yumurta). Kova sürümlüdür: durum
# dosyası bozulursa önceki hâli geri alınabilir.
set -euo pipefail
cd "$(dirname "$0")"

REGION="${AWS_REGION:-us-west-2}"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="evdes-tfstate-${ACCOUNT}"

echo "Hesap: ${ACCOUNT} · bölge: ${REGION} · durum kovası: ${BUCKET}"

if aws s3api head-bucket --bucket "${BUCKET}" 2>/dev/null; then
  echo "Durum kovası zaten var."
else
  if [ "${REGION}" = "us-east-1" ]; then
    aws s3api create-bucket --bucket "${BUCKET}" --region "${REGION}" >/dev/null
  else
    aws s3api create-bucket --bucket "${BUCKET}" --region "${REGION}" \
      --create-bucket-configuration "LocationConstraint=${REGION}" >/dev/null
  fi
  aws s3api put-bucket-versioning --bucket "${BUCKET}" \
    --versioning-configuration Status=Enabled
  aws s3api put-public-access-block --bucket "${BUCKET}" \
    --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
  echo "Durum kovası kuruldu."
fi

if [ ! -f terraform.tfvars ]; then
  cp terraform.tfvars.example terraform.tfvars
  echo "terraform.tfvars oluşturuldu: içindeki alert_email'i kendi adresinle değiştir."
fi

terraform init -backend-config="bucket=${BUCKET}" -backend-config="region=${REGION}"
