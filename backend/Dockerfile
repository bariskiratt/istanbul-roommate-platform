# RoomMatch backend.
# Tek aşama: --fast eğitimi yalnızca runtime bağımlılıklarını kullanır
# (pandas, numpy, lightgbm, scikit-learn), bu yüzden ikinci bir pip kurulumuna
# ve xgboost'un ~300 MB'lık nvidia bağımlılığına gerek yok. Bağımlılık katmanı
# requirements.txt değişmedikçe önbellekten gelir; derleme birkaç dakika sürer.

FROM python:3.12-slim

# LightGBM'in OpenMP çalışma zamanı
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# print() çıktıları tamponlanmadan düşsün. Eğitim adımından ÖNCE tanımlanır:
# aksi halde derleme logunda tüm çıktı en sonda tek seferde görünür ve
# 17 dakikanın nereye gittiği anlaşılmaz.
ENV PYTHONUNBUFFERED=1

# joblib/loky bu konteynerde fiziksel çekirdek sayısını okuyamıyor
# ("found 0 physical cores < 1") ve LightGBM iş parçacığı sayısını oradan
# türetiyor. Sayıyı elle sabitlemek, eğitimin çekirdek algılamasına
# takılmasını önler. Render ücretsiz derleme makinesi 2 çekirdeklidir.
ENV OMP_NUM_THREADS=2 \
    LOKY_MAX_CPU_COUNT=2

# --fast: 4 modelli CV karşılaştırması atlanır (o rapor içindi, yerelde
# `python -m scripts.train_model` ile koşulur); yalnızca servis edilen
# çeyreklik modeller eğitilir.
RUN python -m scripts.train_model --fast

ENV HOST=0.0.0.0
EXPOSE 8000

# --proxy-headers: Render proxy'si arkasında request.base_url https üretsin
# (yoksa yüklenen fotoğraf URL'leri http:// olur ve tarayıcı engeller)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips '*'"]
