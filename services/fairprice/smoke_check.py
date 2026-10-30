"""Dağıtım duman testi: yeni Lambda sürümünün cevabı makul mü?

aws-deploy.yml yeni sürümü `aws lambda invoke --qualifier <sürüm>` ile
smoke-event.json'la çağırır ve cevabı buna verir. Geçmezse `live` takma adı
eski sürümde kalır; yani kullanıcıya giden trafik bozuk sürüme hiç ulaşmaz.

    python services/fairprice/smoke_check.py cevap.json <beklenen-model-sürümü>
"""

import json
import sys
from pathlib import Path

EVENT = Path(__file__).with_name("smoke-event.json")

# İstanbul'da bir dairenin aylık kirası için geniş akıl sınırları (2025-02 TL).
PLAUSIBLE = (2_000, 1_000_000)


def check(response: dict, expected_version: str) -> list[str]:
    problems = []
    if response.get("statusCode") != 200:
        return [f"statusCode {response.get('statusCode')}: {response.get('body')}"]
    body = json.loads(response["body"])
    if body.get("model_version") != expected_version:
        problems.append(
            f"model {body.get('model_version')} sunuluyor, beklenen {expected_version}"
        )
    rows = json.loads(EVENT.read_text())["rows"]
    bands = body.get("bands") or []
    if len(bands) != len(rows):
        problems.append(f"{len(rows)} satıra {len(bands)} bant")
    for i, band in enumerate(bands):
        low, mid, high = band
        if not (PLAUSIBLE[0] <= low <= mid <= high <= PLAUSIBLE[1]):
            problems.append(f"satır {i}: akıl dışı bant {band}")
    return problems


def main() -> int:
    response = json.loads(Path(sys.argv[1]).read_text())
    problems = check(response, sys.argv[2])
    for problem in problems:
        print(f"::error::Duman testi: {problem}")
    if not problems:
        print(f"✅ Duman testi geçti: {json.loads(response['body'])['bands']}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
