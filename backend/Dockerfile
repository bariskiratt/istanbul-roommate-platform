# RoomMatch backend — FastAPI + adil fiyat modeli
# Model dosyası git'te olmadığı için imaj derlenirken eğitilir (~1 dk);
# eğitim verisi (data/) repoda hazır.

FROM python:3.12-slim

# LightGBM'in OpenMP çalışma zamanı
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Adil fiyat modelini üret (models/fair_price_model.joblib)
RUN python -m scripts.train_model

ENV HOST=0.0.0.0
EXPOSE 8000

# --proxy-headers: Render proxy'si arkasında request.base_url https üretsin
# (yoksa yüklenen fotoğraf URL'leri http:// olur ve tarayıcı engeller)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips '*'"]
