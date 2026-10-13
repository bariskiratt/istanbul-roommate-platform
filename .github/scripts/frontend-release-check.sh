#!/usr/bin/env bash
# Frontend'i (Vercel) şu an yayına almak güvenli mi?
#
# main'in en son commit'ine bakar ve iki soruyu sorar:
#   1) CI (ci.yml) bu commit'te yeşil mi?
#   2) Render'da şu an çalışan backend, bu commit'teki backend/ ile aynı mı?
#      "Aynı commit mi" diye değil, "backend/ içeriği aynı mı" diye bakılır:
#      Render backend/'e dokunmayan commit'leri hiç yayına almaz (rootDir), o
#      yüzden yalnızca frontend'i değiştiren bir commit'te yayındaki backend
#      daha eski bir commit'tir ama kodu aynıdır.
# İkisi de evetse frontend bu commit'ten yayına alınabilir; yeni frontend hiçbir
# zaman eski backend'le yan yana çalışmaz.
#
# Sonuç GITHUB_OUTPUT'a yazılır: `sha=<commit>` yayına al, `sha=` (boş) bekle.
# Betik hiçbir şeyi beklemez ya da yoklamaz: Render yayını bitince ya da CI
# bitince iş akışı (frontend-deploy.yml) zaten yeniden tetiklenir.
set -euo pipefail

repo=${GITHUB_REPOSITORY:?}
render_env=${RENDER_ENVIRONMENT:?}
out=${GITHUB_OUTPUT:-/dev/stdout}

git fetch --quiet origin main
head=$(git rev-parse origin/main)

ci=$(gh api -X GET "repos/$repo/actions/workflows/ci.yml/runs" \
  -f head_sha="$head" -f event=push -f per_page=1 \
  --jq '.workflow_runs[0] // {} | "\(.status // "yok")/\(.conclusion // "-")"')
if [ "$ci" != "completed/success" ]; then
  echo "main ${head:0:7}: CI durumu '$ci', yeşil değil. Frontend yayına alınmıyor."
  echo "sha=" >>"$out"
  exit 0
fi

# Render her yayında GitHub'da bir deployment açar (ortam adı: RENDER_ENVIRONMENT).
# En yeniden eskiye: son durumu "success" olan ilk deployment şu an yayında olandır.
# Daha yenisi sürüyor ya da başarısız olduysa Render eskisini sunmaya devam eder.
live=""
while read -r id sha; do
  state=$(gh api "repos/$repo/deployments/$id/statuses?per_page=1" --jq '.[0].state // "yok"')
  if [ "$state" = success ]; then
    live=$sha
    break
  fi
done < <(gh api -X GET "repos/$repo/deployments" \
  -f environment="$render_env" -f per_page=30 --jq '.[] | "\(.id) \(.sha)"')

if [ -z "$live" ]; then
  echo "::warning::Render'da başarılı bir backend yayını bulunamadı (ortam: $render_env). Frontend yayına alınmıyor."
  echo "sha=" >>"$out"
  exit 0
fi

if git diff --quiet "$live" "$head" -- backend; then
  echo "main ${head:0:7}: CI yeşil, Render'daki backend (${live:0:7}) ile backend/ aynı. Frontend yayına alınabilir."
  echo "sha=$head" >>"$out"
else
  echo "main ${head:0:7}: backend/ değişmiş ama Render henüz bu backend'i yayına almadı (yayındaki: ${live:0:7})."
  echo "Frontend bekliyor; Render yayını bitince bu iş akışı yeniden koşacak."
  echo "sha=" >>"$out"
fi
