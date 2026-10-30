"""Eğitilmiş modeli S3'e yükler; kalite kapısından geçerse yayına alır.

Çalıştırma (GitHub Actions, .github/workflows/aws-deploy.yml):
    python -m scripts.train_model --fast
    python -m scripts.publish_model --bucket <kova> --version <sürüm>

S3 düzeni (infra/storage.tf):
    fair-price/<sürüm>/fair_price_model.joblib   model
    fair-price/<sürüm>/metrics.json              ölçümler + sha256 + imza
    fair-price/latest.json                       yayındaki sürümün işaretçisi

Her aday kendi klasörüne yüklenir, reddedilenler de: neden reddedildiği
sonradan bakılabilsin. Yalnızca kapıdan geçen aday latest.json'a yazılır;
backend açılışta, Lambda dağıtımı da imaj derlerken o dosyayı okur. Bir sürüm
klasörü yüklendikten sonra değişmez (aynı adla ikinci yükleme reddedilir):
yayındaki bir Lambda sürümü hangi modeli sabitlediyse o baytlar yerinde kalır.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from botocore.exceptions import ClientError

from app.config import MODEL_METRICS_PATH, MODEL_PATH

PREFIX = "fair-price"
LATEST_KEY = f"{PREFIX}/latest.json"

# Kalite kapısı eşikleri.
# Medyan sapma yayındakinden en fazla bu kadar puan kötü olabilir: aynı veriyle
# yeniden eğitim tek katlı ölçümde ±0,1 puan oynar, bunu red sebebi saymayız.
MAX_MEDAPE_REGRESSION = 0.5
# q25–q75 bandı ayrılmış ilanların kabaca yarısını içermeli (bugün ~%40).
# Bunun çok altı bandın çöktüğünü, çok üstü anlamsız genişlediğini gösterir.
MIN_BAND_COVERAGE, MAX_BAND_COVERAGE = 0.30, 0.70
# Veri dosyası yanlışlıkla kırpılırsa model "iyi" görünse de güvenilmez.
MIN_SAMPLES = 5_000


def gate(candidate: dict, current: dict | None) -> list[str]:
    """Adayın yayına alınmasına engel olan sebepler (boş liste = geçti)."""
    reasons = []
    if candidate["n_samples"] < MIN_SAMPLES:
        reasons.append(
            f"veri {candidate['n_samples']} satır (en az {MIN_SAMPLES} gerekir)"
        )
    coverage = candidate["band_coverage"]
    if not MIN_BAND_COVERAGE <= coverage <= MAX_BAND_COVERAGE:
        reasons.append(
            f"bant kapsaması %{coverage * 100:.0f} "
            f"(%{MIN_BAND_COVERAGE * 100:.0f}–%{MAX_BAND_COVERAGE * 100:.0f} dışında)"
        )
    if current is not None:
        limit = current["served_medape"] + MAX_MEDAPE_REGRESSION
        if candidate["served_medape"] > limit:
            reasons.append(
                f"medyan sapma %{candidate['served_medape']:.2f}, yayındaki "
                f"%{current['served_medape']:.2f} (sınır %{limit:.2f})"
            )
    return reasons


def _read_json(s3, bucket: str, key: str) -> dict | None:
    try:
        body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    except s3.exceptions.NoSuchKey:
        return None
    return json.loads(body)


def _exists(s3, bucket: str, key: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            return False
        raise
    return True


def publish(s3, bucket: str, version: str) -> tuple[bool, list[str], dict]:
    """Adayı yükler, kapıdan geçerse latest.json'u günceller.

    Dönüş: (yayına alındı mı, red sebepleri, latest.json'a yazılan/yazılacak kayıt)
    """
    metrics = json.loads(MODEL_METRICS_PATH.read_text())
    model_key = f"{PREFIX}/{version}/{MODEL_PATH.name}"
    metrics_key = f"{PREFIX}/{version}/metrics.json"
    if _exists(s3, bucket, model_key):
        raise SystemExit(f"{model_key} zaten var; sürüm klasörleri değiştirilmez.")

    s3.upload_file(str(MODEL_PATH), bucket, model_key)
    s3.put_object(
        Bucket=bucket,
        Key=metrics_key,
        Body=json.dumps(metrics, indent=2).encode(),
        ContentType="application/json",
    )

    current = _read_json(s3, bucket, LATEST_KEY)
    reasons = gate(metrics, current)
    record = {
        "version": version,
        "model_key": model_key,
        "metrics_key": metrics_key,
        "sha256": metrics["sha256"],
        "signature": metrics["signature"],
        "served_medape": metrics["served_medape"],
        "band_coverage": metrics["band_coverage"],
        "n_samples": metrics["n_samples"],
        "git_commit": metrics["git_commit"],
        "previous_version": current["version"] if current else None,
        "promoted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if not reasons:
        s3.put_object(
            Bucket=bucket,
            Key=LATEST_KEY,
            Body=json.dumps(record, indent=2).encode(),
            ContentType="application/json",
            # Backend açılışta, dağıtım iş akışı derlemede okur; ara önbellek
            # eski işaretçiyi göstermesin.
            CacheControl="no-cache",
        )
    return not reasons, reasons, record


def _github_output(**values) -> None:
    path = os.getenv("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            for key, value in values.items():
                f.write(f"{key}={value}\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-west-2"))
    args = parser.parse_args(argv)

    import boto3

    s3 = boto3.client("s3", region_name=args.region)
    promoted, reasons, record = publish(s3, args.bucket, args.version)
    _github_output(promoted=str(promoted).lower(), version=args.version)
    print(json.dumps(record, indent=2))
    if promoted:
        print(f"✅ {args.version} yayında (latest.json güncellendi).")
        return 0
    print(f"::error::Kalite kapısı {args.version} sürümünü reddetti: "
          + "; ".join(reasons) + ". Yayındaki model değişmedi.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
