# İstanbul Roommate Platform 🏙️

İstanbul için veri odaklı ev arkadaşı eşleştirme platformu: kaydırmalı (swipe)
bir arayüz, makine öğrenmesiyle **adil kira tahmini**, **bütçe ısı haritası** ve
raylı sistem tabanlı **alternatif semt önerisi** tek uygulamada birleştirir.

İki proje birleştirilmiştir:

- **`frontend/`** — React + TypeScript + Vite + Tailwind + shadcn/ui ile
  yazılmış roommate-finder arayüzü (swipe, eşleşme, sohbet, ilan, profil).
- **`backend/`** — Python + FastAPI; adil fiyat modeli (LightGBM), bütçe ısı
  haritası ve raylı sistem ulaşım grafiğini servis eder.

> **Not (atıf):** Arayüz (`frontend/`) [mirzemirsat/roommate-finder-plus](https://github.com/mirzemirsat/roommate-finder-plus)
> deposundan gelmektedir. Bu monorepo, o arayüzü Python/FastAPI model
> backend'iyle entegre eder.

---

## 🔗 Entegrasyon: model arayüze nasıl bağlandı

Arayüz başta tamamen sahte veriyle çalışıyordu; hiç backend yoktu. Bu birleştirmede
model gerçek anlamda uygulamanın içine girdi:

| Arayüz noktası | Backend ucu | Ne yapar |
|---|---|---|
| **İlan Oluştur → Konum adımı** (`FairPriceCheck`) | `POST /api/estimate` | İlan verenin istediği kirayı, modelin öngördüğü adil aralıkla karşılaştırır ("bu kira %X yüksek"). |
| **Bütçe Haritası sayfası** (`/explore`) | `GET /api/geojson`, `/api/heatmap` | Bütçeye göre mahalleleri yeşil/sarı/kırmızı renklendirir. |
| Aynı sayfada mahalleye tıkla | `GET /api/alternatives` | Pahalı bir semte raylı sistemle yakın, bütçeye uygun alternatif mahalleleri önerir. |

Arayüz backend'e `frontend/src/lib/api.ts` üzerinden bağlanır; adres
`VITE_API_URL` ile ayarlanır (`frontend/.env.example`).

---

## ▶️ Çalıştırma (iki terminal)

**1) Backend** (http://127.0.0.1:8000)

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

python -m scripts.train_model     # adil fiyat modelini üretir (~1 dk, ilk sefer)
python -m app.main
```

macOS'ta LightGBM için: `brew install libomp`. Toplu taşıma verisi depoda
hazırdır; yeniden indirmek istersen `python -m scripts.fetch_transit`.

**2) Frontend** (http://localhost:8080)

```bash
cd frontend
npm install
cp .env.example .env          # VITE_API_URL zaten 127.0.0.1:8000
npm run dev
```

Tarayıcıda **http://localhost:8080** → üst menüde **Bütçe Haritası**, ya da
**İlan Oluştur → Ev İlanı → Konum** adımında adil fiyat danışmanı.

---

## 🧠 Modeller ve yöntem

Ayrıntılar `backend/README.md` içinde. Özet:

- **Adil fiyat (Modül 1):** hedef `log(kira)`; LightGBM çeyreklik regresyonu
  (q25/q50/q75) ile nokta değil **aralık** verir. 5-kat CV medyan sapma
  **%15.1** (mahalle-medyanı referansı %25).
- **Bütçe ısı haritası (Modül 2):** 968 mahalle sınırı; Türkçe-duyarlı adres
  eşleştirmesiyle fiyat verisine bağlanır. İstek başına ~600 B (geometri ayrı,
  bir kez indirilir).
- **Alternatif semt (Modül 3):** raylı sistem ağı üzerinde aktarma-ağırlıklı en
  kısa yol (durak=1, aktarma=+5). Kuş uçuşu mesafe değil ağ maliyeti kullanılır
  (Boğaz sorunu). Veri OpenStreetMap/Overpass'ten (ODbL).

---

## 📂 Yapı

```
backend/        FastAPI + modeller (kendi README'si var)
  app/          API, model servisi, ulaşım grafiği
  scripts/      offline üreticiler (eğitim, veri, ulaşım)
  data/ models/ veri ve eğitilmiş model
frontend/       React/Vite roommate arayüzü
  src/lib/api.ts        backend istemcisi
  src/pages/Explore.tsx bütçe haritası + alternatifler
  src/components/FairPriceCheck.tsx  adil fiyat danışmanı
```

## ⚠️ Sınırlar

- Model tahminleri ekspertiz değildir; veri dönemi CSV'de belirtilmemiştir.
- Ulaşım yalnızca raylı sistem (metrobüs/otobüs/vapur hariç).
- Roommate arayüzünün eşleşme/sohbet/profil kısımları hâlâ sahte veriyle çalışır;
  bu birleştirmede backend'e bağlanan kısım fiyat modeli ve haritadır.
