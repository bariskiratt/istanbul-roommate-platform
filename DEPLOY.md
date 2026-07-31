# Yayına Alma (Deploy)

Mimari: **backend → Render** (Docker + ücretsiz Postgres), **frontend → Vercel**.
Kod tarafı hazır; aşağıdaki adımlar hesap açıp bağlamaktan ibaret.

## 1) Backend — Render

1. https://render.com → GitHub ile giriş yap.
2. **New → Blueprint** → `istanbul-roommate-platform` reposunu seç.
   Kökteki `render.yaml` otomatik okunur: `roommatch-api` servisi + `roommatch-db`
   Postgres'i kurulur. Docker imajı derlenirken adil fiyat modeli eğitilir (~5-10 dk).
3. Kurulum bittiğinde API adresini not al: `https://roommatch-api.onrender.com` gibi.
4. Service → Environment → `CORS_ORIGINS` değerine Vercel adresini gir
   (2. bölümü bitirince): `https://SENIN-PROJEN.vercel.app`

Notlar:
- **Fotoğraflar:** Ücretsiz planda disk kalıcı değildir — yüklenen fotoğraflar
  yeniden dağıtımda silinir. Kalıcılık için: Render'da ücretli disk ekleyip
  `UPLOADS_DIR` env'ini o yola ver, ya da (daha iyisi) S3/Cloudflare R2
  entegrasyonu yap (sonraki iş).
- **Uyku modu:** Ücretsiz web servisi 15 dk hareketsizlikte uyur; ilk istek
  ~1 dk gecikebilir.
- **Demo içerik:** İstersen Render Shell'den `python -m scripts.seed_demo`
  çalıştırarak 100 demo ilanı ekleyebilirsin.

## 2) Frontend — Vercel

1. https://vercel.com → GitHub ile giriş → **Add New → Project** → repoyu seç.
2. **Root Directory:** `frontend` olarak ayarla (Vite otomatik algılanır).
3. Environment Variables: `VITE_API_URL` = Render API adresin
   (ör. `https://roommatch-api.onrender.com`).
4. Deploy. Çıkan adresi Render'daki `CORS_ORIGINS`'e yaz (1. bölüm, 4. adım).

## 3) Kontrol listesi

- [ ] `https://API-ADRESIN/` → endpoint listesi dönüyor
- [ ] `https://API-ADRESIN/docs` → Swagger açılıyor
- [ ] Vercel adresinde Bütçe Haritası yükleniyor (CORS doğru demektir)
- [ ] Kayıt akışı çalışıyor (OTP dev modda toast'ta görünür)

## 4) Yayın öncesi bilinen eksikler

| Konu | Durum |
|---|---|
| OTP e-postası | Brevo entegrasyonu hazır (`app/emailer.py`). Aktifleştirme: Brevo hesabı aç → gönderici e-postanı doğrula → API key al → Render env: `BREVO_API_KEY`, `EMAIL_FROM`, `DEV_OTP=0`. Bunlar ayarlanmadan `DEV_OTP=1` kalmalı. |
| Fotoğraf depolama | Yerel disk; kalıcı depolama (R2/S3) gerekli. |
| Rate limiting / token süresi | Yok; yayın sonrası ilk sertleştirme adımı. |
| Uyku modu | `.github/workflows/keepalive.yml` 10 dakikada bir API'yi yoklayarak ücretsiz servisi uyanık tutar. |

## Ortam değişkenleri özeti (backend)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `DATABASE_URL` | `sqlite:///data/app.db` | Postgres bağlantısı (Render otomatik verir) |
| `CORS_ORIGINS` | localhost listesi | Virgülle ayrılmış izinli origin'ler |
| `DEV_OTP` | `1` | 1: OTP kodu API yanıtında döner (dev) |
| `BREVO_API_KEY` | — | Brevo API anahtarı (gerçek OTP e-postası) |
| `EMAIL_FROM` | — | Brevo'da doğrulanmış gönderici adresi |
| `UPLOADS_DIR` | `data/uploads` | Fotoğrafların yazıldığı dizin |
| `PORT` / `HOST` | `8000` / `127.0.0.1` | Sunucu adresi (Render PORT verir) |
| `RENT_INDEX_FACTOR` | (tablodan) | TÜFE çarpanını elle sabitleme |
