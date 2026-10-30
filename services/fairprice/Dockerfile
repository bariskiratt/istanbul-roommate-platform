# Adil kira tahmin servisi: AWS Lambda konteyner imajı.
#
# Derleme bağlamı REPO KÖKÜ (backend/app/pricing.py imaja kopyalanır):
#   docker build -f services/fairprice/Dockerfile \
#     --build-arg MODEL_VERSION=<sürüm> --build-arg MODEL_SHA256=<sha256> .
#
# Zip yerine imaj: LightGBM + scikit-learn + SciPy + pandas açılmış hâlde
# Lambda'nın 250 MB'lık zip sınırını aşıyor; imaj sınırı 10 GB.
ARG BASE_IMAGE=public.ecr.aws/lambda/python:3.12
FROM ${BASE_IMAGE}

# LightGBM'in OpenMP çalışma zamanı (backend/Dockerfile'daki libgomp1'in
# Amazon Linux karşılığı). Taban imajda zaten varsa paket deposuna gidilmez.
RUN [ -e /usr/lib64/libgomp.so.1 ] || (dnf install -y libgomp && dnf clean all)

COPY services/fairprice/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt --target "${LAMBDA_TASK_ROOT}" \
    && rm /tmp/requirements.txt \
    # Paketlerin kendi testleri ve önbellekleri yalnızca yer kaplar; imaj
    # küçüldükçe soğuk başlangıç kısalır. (Taban imajda `find` yok.)
    && python -c "import pathlib, shutil, sys; \
[shutil.rmtree(p, ignore_errors=True) for p in list(pathlib.Path(sys.argv[1]).rglob('*')) \
 if p.name in ('tests', '__pycache__') and p.is_dir()]" "${LAMBDA_TASK_ROOT}"

# Özellik üretimi backend'le PAYLAŞILIR, kopyası yazılmaz: aynı dosya.
COPY backend/app/__init__.py backend/app/config.py backend/app/pricing.py ${LAMBDA_TASK_ROOT}/app/
COPY services/fairprice/handler.py ${LAMBDA_TASK_ROOT}/

# Bu imajın sunacağı model; dağıtım iş akışı latest.json'dan okuyup verir.
# Boşsa (yerel deneme) MODEL_PATH ile diskteki model kullanılır.
ARG MODEL_VERSION=""
ARG MODEL_SHA256=""
# JOBLIB_MULTIPROCESSING=0: Lambda'da /dev/shm yok; joblib her soğuk
# başlangıçta bunu deneyip uyarı yazmasın (zaten tek iş parçacığıyla çalışıyor).
ENV MODEL_VERSION=${MODEL_VERSION} \
    MODEL_SHA256=${MODEL_SHA256} \
    OMP_NUM_THREADS=1 \
    JOBLIB_MULTIPROCESSING=0

CMD ["handler.handler"]
