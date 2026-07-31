# RoomMatch backend — çok aşamalı derleme.
# 1) builder: eğitim bağımlılıklarıyla (sklearn/xgboost) model eğitilir.
# 2) runtime: yalnız servis bağımlılıkları + eğitilmiş model — imaj ~400 MB
#    daha küçük ve requirements değişmedikçe katman önbellekten gelir.

FROM python:3.12-slim AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .
# --fast: CV karşılaştırması yerelde/CI'da koşulur; imaj derlemesinde yalnız
# servis edilen modeller eğitilir (zayıf derleyicide ~40 dk -> ~3 dk)
RUN python -m scripts.train_model --fast

# ---- runtime ----
FROM python:3.12-slim

# LightGBM'in OpenMP çalışma zamanı
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=builder /app/models/fair_price_model.joblib models/

ENV HOST=0.0.0.0
EXPOSE 8000

# --proxy-headers: Render proxy'si arkasında request.base_url https üretsin
# (yoksa yüklenen fotoğraf URL'leri http:// olur ve tarayıcı engeller)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips '*'"]
