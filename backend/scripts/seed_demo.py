"""Demo içerik üretici: 20 sahte kullanıcı + 100 gerçekçi ilan.

Kiralar gerçek mahalle medyanlarından türetilir
(data/processed/neighborhood_market_values.csv) ve TÜFE ile bugüne
endekslenir; böylece adil fiyat danışmanıyla tutarlı kalırlar.

Çalıştırma:  python -m scripts.seed_demo          (tekrar çalıştırmak eklemez)
             python -m scripts.seed_demo --force  (demo verisini silip yeniden üretir)
"""

import random
import sys

import pandas as pd

from app import models
from app.auth import _hash_password
from app.config import MARKET_VALUES_CSV
from app.db import SessionLocal, init_db
from app.indexing import rent_index

DEMO_DOMAIN = "demo.roommatch.tr"  # demo hesaplar bu alan adından tanınır

# (ad, cinsiyet) — portre fotoğrafı cinsiyetle tutarlı seçilir
PEOPLE = [
    ("Elif", "kadın"), ("Zeynep", "kadın"), ("Defne", "kadın"),
    ("Azra", "kadın"), ("Ecrin", "kadın"), ("Selin", "kadın"),
    ("Melis", "kadın"), ("İrem", "kadın"), ("Ceren", "kadın"),
    ("Buse", "kadın"), ("Mert", "erkek"), ("Emir", "erkek"),
    ("Kerem", "erkek"), ("Arda", "erkek"), ("Deniz", "erkek"),
    ("Ege", "erkek"), ("Baran", "erkek"), ("Can", "erkek"),
    ("Kaan", "erkek"), ("Umut", "erkek"),
]

def _portrait(gender: str, idx: int) -> str:
    """randomuser.me portreleri: cinsiyete uygun, sabit (0-99 arası)."""
    kind = "women" if gender == "kadın" else "men"
    return f"https://randomuser.me/api/portraits/{kind}/{(idx * 7 + 3) % 99}.jpg"

# Ev ilanları için elle seçilmiş iç mekân fotoğrafları (Unsplash, stabil id'ler)
HOME_PHOTOS = [
    "photo-1502672260266-1c1ef2d93688",  # salon, aydınlık
    "photo-1522708323590-d24dbb6b0267",  # modern oturma odası
    "photo-1560448204-e02f11c3d0e2",     # stüdyo daire
    "photo-1493809842364-78817add7ffb",  # salon, kanepe
    "photo-1484154218962-a197022b5858",  # mutfak-salon
    "photo-1586023492125-27b2c045efd7",  # oturma odası, bitkili
    "photo-1512918728675-ed5a9ecdebfd",  # yatak odası
    "photo-1554995207-c18c203602cb",     # salon, minimal
]

def _home_photo(seed: int) -> str:
    pid = HOME_PHOTOS[seed % len(HOME_PHOTOS)]
    return f"https://images.unsplash.com/{pid}?w=640&h=480&fit=crop"
UNIVERSITIES = [
    "Boğaziçi Üniversitesi", "İTÜ", "Marmara Üniversitesi", "Yıldız Teknik",
    "İstanbul Üniversitesi", "Koç Üniversitesi", "Sabancı Üniversitesi",
    "Galatasaray Üniversitesi", "Bahçeşehir Üniversitesi", "Bilgi Üniversitesi",
]
DEPARTMENTS = [
    "Bilgisayar Mühendisliği", "Psikoloji", "Hukuk", "Tıp", "Mimarlık",
    "İşletme", "Endüstri Mühendisliği", "Sosyoloji", "İktisat",
    "Elektrik-Elektronik Müh.", "Grafik Tasarım", "Moleküler Biyoloji",
]
BIOS = [
    "Sabahçıyım, ev düzenine önem veririm. Sessiz bir çalışma ortamı arıyorum.",
    "Kitap ve kahve düşkünü. Hafta sonları genelde evdeyim.",
    "Sporla ilgileniyorum, erken kalkarım. Temizlik konusunda titizim.",
    "Müzik yapıyorum ama kulaklıkla çalışırım, merak etme.",
    "Yemek yapmayı severim, mutfağı paylaşmaktan mutluluk duyarım.",
    "Sakin, anlaşması kolay biriyim. Uzun dönem ev arkadaşı arıyorum.",
    "Yüksek lisans öğrencisiyim, günümün çoğu kampüste geçiyor.",
    "Dizi maratonlarına ortak arıyorum ama ders dönemi sessizlik esas.",
]
EV_TITLES = [
    "{n} güneşli {r} — oda arkadaşı arıyorum",
    "{d} merkezde ferah {r}, 1 oda boş",
    "{n} temiz ve eşyalı {r}",
    "Metroya yakın {r}, ev arkadaşı aranıyor",
    "{d} öğrenci dostu {r}, hemen taşınılır",
    "{n} sessiz sokakta {r}",
]
EV_DESCS = [
    "Ev aydınlık ve eşyalı. Ortak alanları birlikte kullanıyoruz, faturalar bölüşülüyor. Durak 5 dk.",
    "Oda geniş, gardırop ve çalışma masası mevcut. İnternet dahil. Uzun dönem tercihimiz.",
    "Binada asansör var, market ve kafeler yürüme mesafesinde. Depozito 1 kira.",
    "Ev arkadaşım mezun olup taşındığı için odası boşaldı. Düzenli ve sakin bir ev.",
    "Kampüse tek vasıta. Isınma merkezi, aidat düşük. Görmeye gelebilirsin.",
]
KISISEL_TITLES = [
    "{d} civarında oda arıyorum",
    "Ekim başı için ev arkadaşı arayışındayım",
    "{d} ya da çevresinde paylaşımlı ev arıyorum",
    "Sessiz bir oda arıyorum ({d} tercihim)",
]
KISISEL_DESCS = [
    "Bütçeme uygun, ulaşımı rahat bir oda arıyorum. Kendi eşyam yok, eşyalı tercih ederim.",
    "Okula yakın bir yer arıyorum. Temiz ve düzenliyim, referans verebilirim.",
    "Staja başladım, hafta içi yoğunum. Sakin bir ev ortamı önceliğim.",
    "İkinci sınıf öğrencisiyim, yurttan eve geçmek istiyorum.",
]

ROOM_OPTIONS = ["1+1", "2+1", "2+1", "3+1"]  # 2+1 ağırlıklı


def seed(force: bool = False) -> None:
    init_db()
    db = SessionLocal()
    factor, _ = rent_index()

    demo_users = (
        db.query(models.User).filter(models.User.email.like(f"%@{DEMO_DOMAIN}")).all()
    )
    if demo_users and not force:
        print(f"Zaten {len(demo_users)} demo kullanıcı var — çıkılıyor. "
              f"Yeniden üretmek için: --force")
        db.close()
        return
    if demo_users and force:
        ids = [u.id for u in demo_users]
        # Önce demo eşleşmelerine ait TÜM mesajlar (karşı taraf gerçek kullanıcı
        # olsa bile) silinmeli; yoksa Postgres FK ihlaliyle durur.
        match_ids = [
            m.id
            for m in db.query(models.Match.id).filter(
                (models.Match.user_a_id.in_(ids))
                | (models.Match.user_b_id.in_(ids))
            )
        ]
        if match_ids:
            db.query(models.Message).filter(
                models.Message.match_id.in_(match_ids)
            ).delete(synchronize_session=False)
        db.query(models.Match).filter(
            (models.Match.user_a_id.in_(ids)) | (models.Match.user_b_id.in_(ids))
        ).delete(synchronize_session=False)
        listing_ids = [
            l.id
            for u in demo_users
            for l in db.query(models.Listing).filter_by(owner_id=u.id)
        ]
        if listing_ids:
            db.query(models.Swipe).filter(
                models.Swipe.listing_id.in_(listing_ids)
            ).delete(synchronize_session=False)
        db.query(models.Swipe).filter(
            models.Swipe.swiper_id.in_(ids)
        ).delete(synchronize_session=False)
        db.query(models.Listing).filter(
            models.Listing.owner_id.in_(ids)
        ).delete(synchronize_session=False)
        db.query(models.AuthToken).filter(
            models.AuthToken.user_id.in_(ids)
        ).delete(synchronize_session=False)
        for u in demo_users:
            db.delete(u)
        db.commit()
        print(f"♻️  Eski demo verisi silindi ({len(demo_users)} kullanıcı).")

    market = pd.read_csv(MARKET_VALUES_CSV)
    # En az 10 ilanlık mahalleler — medyanı daha güvenilir
    market = market[market["total_listings"] >= 10].reset_index(drop=True)

    # --- 20 demo kullanıcı ---
    users: list[models.User] = []
    for i, (name, gender) in enumerate(PEOPLE):
        row = market.sample(1).iloc[0]
        budget_mid = row["avg_price"] * factor / random.choice([2, 2, 3])
        b_min = int(round(budget_mid * 0.8, -2))
        b_max = int(round(budget_mid * 1.25, -2))
        user = models.User(
            email=f"demo{i + 1}@{DEMO_DOMAIN}",
            password_hash=_hash_password("Demo1234!"),
            verified=True,
            name=name,
            gender=gender,
            birth_year=random.randint(1999, 2006),
            university=random.choice(UNIVERSITIES),
            department=random.choice(DEPARTMENTS),
            year=random.randint(1, 4),
            budget_min=b_min,
            budget_max=b_max,
            smoking=random.random() < 0.25,
            pets=random.random() < 0.4,
            alcohol=random.random() < 0.5,
            sleep_schedule=random.choice(["erken", "gece", "esnek"]),
            preferred_districts=[str(row["district"])],
            bio=random.choice(BIOS),
            photos=[_portrait(gender, i)],
        )
        db.add(user)
        users.append(user)
    db.flush()

    # --- 100 ilan: 60 ev + 40 kişisel ---
    created = 0
    for i in range(100):
        owner = users[i % len(users)]
        row = market.sample(1).iloc[0]
        district = str(row["district"]).strip()
        neighborhood = str(row["neighborhood"]).strip()
        is_house = i < 60

        if is_house:
            rooms = random.choice(ROOM_OPTIONS)
            n_rooms = int(rooms[0])
            # Oda payı = endeksli daire kirası / oda sayısı, ±%15 oynama
            share = row["avg_price"] * factor / max(n_rooms, 1)
            rent = int(round(share * random.uniform(0.85, 1.15), -2))
            listing = models.Listing(
                owner_id=owner.id,
                type="ev_ilani",
                title=random.choice(EV_TITLES).format(
                    d=district, n=neighborhood.replace(" Mah.", ""), r=rooms
                ),
                description=random.choice(EV_DESCS),
                district=district,
                rent=rent,
                room_count=rooms,
                smoking_allowed=random.random() < 0.2,
                pets_allowed=random.random() < 0.45,
                photos=[
                    _home_photo(i + k) for k in range(random.randint(1, 3))
                ],
            )
        else:
            mid = row["avg_price"] * factor / random.choice([2, 2, 3])
            listing = models.Listing(
                owner_id=owner.id,
                type="kisisel_ilan",
                title=random.choice(KISISEL_TITLES).format(d=district),
                description=random.choice(KISISEL_DESCS),
                district=district,
                budget_min=int(round(mid * 0.8, -2)),
                budget_max=int(round(mid * 1.25, -2)),
                # İlan görseli iç mekân olsun; sahibinin portresi profil/deste
                # şeritlerinde zaten görünüyor (Evler sayfasında yüz garip duruyor)
                photos=[_home_photo(i)],
            )
        db.add(listing)
        created += 1

    db.commit()
    print(f"✅ {len(users)} demo kullanıcı + {created} ilan eklendi "
          f"(kiralar TÜFE x{factor:.4f} ile endeksli).")
    db.close()


if __name__ == "__main__":
    seed(force="--force" in sys.argv)
