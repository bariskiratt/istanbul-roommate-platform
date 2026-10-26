# Model kovası: her eğitilmiş model kendi klasöründe, yayındaki işaretçi
# fair-price/latest.json (düzen: backend/scripts/publish_model.py).
resource "aws_s3_bucket" "models" {
  bucket = "${var.project}-models-${local.account_id}"

  # `terraform destroy` kovayı içindekilerle siler. Bilerek: modeller
  # depodaki veriden ~10 saniyede yeniden eğitilebilir, saklanan tek şey onlar.
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "models" {
  bucket                  = aws_s3_bucket.models.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "models" {
  bucket = aws_s3_bucket.models.id
  rule {
    object_ownership = "BucketOwnerEnforced" # ACL yok, yetki yalnızca IAM'den
  }
}

resource "aws_s3_bucket_versioning" "models" {
  bucket = aws_s3_bucket.models.id
  versioning_configuration {
    status = "Enabled" # latest.json yanlışlıkla ezilse de önceki hâli geri alınabilir
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "models" {
  bucket = aws_s3_bucket.models.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "models" {
  bucket = aws_s3_bucket.models.id

  rule {
    id     = "eski-nesne-surumleri"
    status = "Enabled"
    filter {}

    # Yalnızca ezilmiş/silinmiş nesnelerin eski hâlleri gider; model
    # klasörleri hiç ezilmediği için (publish_model.py) dokunulmaz.
    noncurrent_version_expiration {
      noncurrent_days = 30
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

data "aws_iam_policy_document" "models_bucket" {
  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.models.arn, "${aws_s3_bucket.models.arn}/*"]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "models" {
  bucket = aws_s3_bucket.models.id
  policy = data.aws_iam_policy_document.models_bucket.json

  depends_on = [aws_s3_bucket_public_access_block.models]
}
