"""Demo içerik üretici: 5 kullanıcı + 5 özenli ilan.

Az ama dolu dolu: her ilan elle yazılmış (gerçek semt, çok fotoğraflı,
ayrıntılı açıklama). Kiralar mahalle medyanlarından türetilip
(data/processed/neighborhood_market_values.csv) TÜFE ile bugüne endekslenir;
böylece adil fiyat danışmanıyla tutarlı kalırlar.

Çalıştırma:  python -m scripts.seed_demo          (tekrar çalıştırmak eklemez)
             python -m scripts.seed_demo --force  (demo verisini silip yeniden üretir)
"""

import sys

import pandas as pd

from app import models
from app.auth import _hash_password
from app.config import MARKET_VALUES_CSV
from app.db import SessionLocal, init_db
from app.indexing import rent_index

DEMO_DOMAIN = "demo.roommatch.tr"  # demo hesaplar bu alan adından tanınır


def _unsplash(photo_id: str) -> str:
    return f"https://images.unsplash.com/{photo_id}?w=900&h=675&fit=crop"


def _portrait(kind: str, n: int) -> str:
    return f"https://randomuser.me/api/portraits/{kind}/{n}.jpg"


# --- 5 demo kullanıcı (profilleri eksiksiz) ---
PEOPLE = [
    {
        "name": "Elif", "budget": (18000, 30000), "gender": "kadın", "birth_year": 2003,
        "university": "Boğaziçi Üniversitesi", "department": "Psikoloji", "year": 3,
        "smoking": False, "alcohol": False, "pets": True, "sleep": "erken",
        "bio": "Kitap kurdu, sabah insanıyım. Ev düzenine önem veririm ama "
               "kurallarla boğmam; sadece paylaşılan alanların temiz kalmasını "
               "isterim. Hafta sonları genelde evdeyim, kahve demleyip ders çalışırım.",
        "photo": _portrait("women", 44),
        "districts": ["Beşiktaş", "Sarıyer"],
    },
    {
        "name": "Mert", "budget": (12000, 20000), "gender": "erkek", "birth_year": 2002,
        "university": "İstanbul Teknik Üniversitesi",
        "department": "Bilgisayar Mühendisliği", "year": 4,
        "smoking": False, "alcohol": True, "pets": True, "sleep": "gece",
        "bio": "Son sınıf öğrencisiyim, yarı zamanlı yazılım işim var. Geceleri "
               "kod yazarım ama kulaklıkla. Mutfağı severim, hafta içi akşam "
               "yemeğini genelde ben yaparım — ortak yemek kültürüne varım.",
        "photo": _portrait("men", 32),
        "districts": ["Şişli", "Beşiktaş"],
    },
    {
        "name": "Zeynep", "budget": (15000, 26000), "gender": "kadın", "birth_year": 2004,
        "university": "Marmara Üniversitesi", "department": "Hukuk", "year": 2,
        "smoking": False, "alcohol": False, "pets": False, "sleep": "erken",
        "bio": "Sessiz ve düzenliyim. Sınav dönemlerinde eve kapanırım, onun "
               "dışında sosyalim. Aynı evde yaşadığım kişiyle arkadaş olmayı "
               "isterim, sadece fatura paylaşan iki yabancı gibi değil.",
        "photo": _portrait("women", 68),
        "districts": ["Kadıköy", "Üsküdar"],
    },
    {
        "name": "Kerem", "budget": (16000, 28000), "gender": "erkek", "birth_year": 2001,
        "university": "Yıldız Teknik Üniversitesi",
        "department": "Endüstri Mühendisliği", "year": 4,
        "smoking": True, "alcohol": True, "pets": False, "sleep": "esnek",
        "bio": "Yüksek lisansa hazırlanıyorum, gündüzlerim kampüste geçiyor. "
               "Balkonda sigara içerim, evde içmem. Spor salonuna yakın bir yer "
               "arıyorum; hafta sonları basketbol oynarım.",
        "photo": _portrait("men", 51),
        "districts": ["Beşiktaş", "Şişli"],
    },
    {
        "name": "Defne", "budget": (14000, 24000), "gender": "kadın", "birth_year": 2003,
        "university": "İstanbul Üniversitesi", "department": "Mimarlık", "year": 3,
        "smoking": False, "alcohol": True, "pets": True, "sleep": "gece",
        "bio": "Mimarlık öğrencisiyim, maket ve çizim için geniş bir masaya "
               "ihtiyacım var. Gece geç saatlere kadar çalışırım ama sessizim. "
               "Kedim Zeytin benimle geliyor — hayvan dostu ev şart.",
        "photo": _portrait("women", 12),
        "districts": ["Kadıköy", "Beyoğlu"],
    },
]

# --- 5 ilan: 4 ev + 1 kişisel, hepsi elle yazılmış ---
LISTINGS = [
    {
        "owner": 0,
        "type": "ev_ilani",
        "district": "Beşiktaş",
        "neighborhood": "Etiler Mah.",
        "rooms": "2+1",
        "title": "Etiler'de aydınlık 2+1 — bir oda boş, kampüse 10 dk",
        "description": (
            "Boğaziçi Güney Kampüs'e yürüme mesafesinde, sakin bir sokakta "
            "2+1 dairede oda arkadaşı arıyorum. Ev güney cepheli, gün boyu "
            "güneş alıyor.\n\n"
            "Boşalan oda 14 m²; içinde gardırop, çalışma masası ve tek kişilik "
            "yatak mevcut. Salon ortak, ben genelde odamda çalıştığım için "
            "salonu rahatça kullanabilirsin.\n\n"
            "Bina asansörlü ve kapıcılı. Doğalgaz kombi (fatura ortak), "
            "internet fiber ve kiraya dahil. Markete ve metrobüse 5 dakika.\n\n"
            "Aidat 1.200 TL, ortalama fatura kişi başı ~1.500 TL. Depozito bir "
            "kira. En az iki dönem kalmayı düşünen birini tercih ederim."
        ),
        "photos": [
            "photo-1502672260266-1c1ef2d93688",  # salon
            "photo-1512918728675-ed5a9ecdebfd",  # yatak odası
            "photo-1556911220-bff31c812dba",     # mutfak
            "photo-1600566753190-17f0baa2a6c3",  # oda detay
            "photo-1584622650111-993a426fbf0a",  # banyo
        ],
        "smoking": False,
        "pets": True,
    },
    {
        "owner": 1,
        "type": "ev_ilani",
        "district": "Şişli",
        "neighborhood": "Mecidiyeköy Mah.",
        "rooms": "3+1",
        "title": "Mecidiyeköy metroya 3 dk, 3+1 dairede geniş oda",
        "description": (
            "Metro çıkışına 3 dakika yürüme mesafesinde, 3+1 dairede tek kişilik "
            "oda. Şu an iki kişiyiz (ben ve bir arkadaşım), üçüncü ev arkadaşımızı "
            "arıyoruz.\n\n"
            "Oda 16 m², bina cephesine bakıyor ve gürültü almıyor — çift cam var. "
            "Eşyalı: yatak, dolap, kitaplık, çalışma masası.\n\n"
            "Ev tamamen eşyalı ve yeni tadilatlı. Bulaşık makinesi, çamaşır "
            "makinesi, klima mevcut. Mutfak geniş, birlikte yemek yapmayı seven "
            "biri olursa çok memnun oluruz.\n\n"
            "İTÜ, YTÜ ve Bilgi kampüslerine tek vasıta. Depozito bir kira, "
            "faturalar üçe bölünüyor (kişi başı ~1.200 TL)."
        ),
        "photos": [
            "photo-1522708323590-d24dbb6b0267",  # oturma odası
            "photo-1554995207-c18c203602cb",     # salon
            "photo-1586023492125-27b2c045efd7",  # oturma alanı
            "photo-1560448204-e02f11c3d0e2",     # stüdyo
        ],
        "smoking": False,
        "pets": False,
    },
    {
        "owner": 2,
        "type": "ev_ilani",
        "district": "Kadıköy",
        "neighborhood": "Caferağa Mah.",
        "rooms": "2+1",
        "title": "Moda'da deniz kokan 2+1 — sessiz ev arkadaşı aranıyor",
        "description": "",  # aşağıda doldurulur
        "photos": [
            "photo-1493809842364-78817add7ffb",
            "photo-1484154218962-a197022b5858",
            "photo-1505873242700-f289a29e1e0f",
            "photo-1616486338812-3dadae4b4ace",
        ],
        "smoking": False,
        "pets": False,
    },
    {
        "owner": 4,
        "type": "ev_ilani",
        "district": "Beyoğlu",
        "neighborhood": "Cihangir Mah.",
        "rooms": "2+1",
        "title": "Cihangir'de tarihi binada 2+1 — mimarlık öğrencisi ev sahibi",
        "description": (
            "Cihangir'in ara sokaklarından birinde, 1950'ler binasında yüksek "
            "tavanlı 2+1. Ev karakterli: ahşap zemin, büyük pencereler, küçük bir "
            "Fransız balkonu.\n\n"
            "Boşalan oda 13 m², içinde geniş bir çalışma masası var (mimarlık/"
            "tasarım öğrencisiyseniz maket için ideal). Yatak ve dolap mevcut.\n\n"
            "Kedim Zeytin bizimle yaşıyor, uysal ve temiz — hayvan sevmeyen biri "
            "için uygun değil. Ev sıcak, kalorifer merkezi.\n\n"
            "Taksim'e yürüme mesafesi, gece hayatının içinde ama sokak sakin. "
            "MSGSÜ ve İTÜ Taşkışla'ya yürüyerek gidilebiliyor. Aidat 900 TL."
        ),
        "photos": [
            "photo-1560448204-e02f11c3d0e2",     # yüksek tavanlı salon
            "photo-1502672260266-1c1ef2d93688",  # aydınlık oda
            "photo-1586023492125-27b2c045efd7",  # oturma alanı
            "photo-1512918728675-ed5a9ecdebfd",  # yatak odası
            "photo-1505873242700-f289a29e1e0f",  # çalışma köşesi
        ],
        "smoking": False,
        "pets": True,
    },
    {
        "owner": 3,
        "type": "kisisel_ilan",
        "district": "Beşiktaş",
        "neighborhood": "Levent Mah.",
        "rooms": None,
        "title": "Beşiktaş / Levent civarında oda arıyorum — 4. sınıf öğrencisi",
        "description": (
            "YTÜ Endüstri son sınıf öğrencisiyim, eylül döneminde taşınmak için "
            "oda arıyorum. Beşiktaş, Levent, Etiler ve Şişli çevresine bakıyorum; "
            "metroya yakın olması benim için önemli.\n\n"
            "Kendimden: düzenliyim, bulaşığı biriktirmem, ortak alanları "
            "temiz tutarım. Balkonda sigara içerim, evde içmem. Hafta içi gündüz "
            "kampüste oluyorum, akşamları genelde evdeyim.\n\n"
            "Uzun dönem (en az 1 yıl) kalmayı planlıyorum. Kefil ve gelir belgesi "
            "sunabilirim. Eşyalı bir oda tercih ederim ama şart değil.\n\n"
            "Ev arkadaşımla ara sıra yemek yiyip film izleyebileceğimiz, ama "
            "birbirimizin alanına da saygı duyduğumuz bir düzen ideal."
        ),
        "photos": [
            "photo-1522708323590-d24dbb6b0267",
            "photo-1554995207-c18c203602cb",
        ],
        "smoking": True,
        "pets": False,
    },
]

LISTINGS[2]["description"] = (
    "Moda sahiline 6 dakika, Bahariye'ye 8 dakika yürüme mesafesinde 2+1 daire. "
    "Ev arkadaşım mezun olup şehir değiştirdiği için odası boşaldı.\n\n"
    "Oda 15 m², parke zemin, çift kişilik yatak ve büyük gardırop var. Sokak "
    "cephesine bakıyor ama üst kat olduğu için sessiz.\n\n"
    "Ben hukuk öğrencisiyim, sınav dönemlerinde eve kapanırım — benzer şekilde "
    "sessizliğe önem veren biriyle yaşamak isterim. Evde parti/kalabalık "
    "misafir düzeni yok, ara sıra 2-3 kişilik kahve sohbetleri olur.\n\n"
    "Bina 12 yaşında, asansörlü. Kombi bireysel, faturalar ikiye bölünüyor "
    "(kişi başı ~1.400 TL). Marmaray ve metroya yürüme mesafesi; Marmara "
    "Göztepe kampüsüne tek vasıta. Depozito bir kira."
)


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

    def median_rent(district: str, neighborhood: str, rooms: str | None) -> int:
        """Mahalle medyanını TÜFE ile endeksleyip oda payına böler."""
        row = market[
            (market["district"].str.strip() == district)
            & (market["neighborhood"].str.strip() == neighborhood)
        ]
        if row.empty:  # mahalle yoksa ilçe medyanı
            row = market[market["district"].str.strip() == district]
        base = float(row["avg_price"].median()) * factor
        share = int(rooms[0]) if rooms else 2
        return int(round(base / max(share, 1), -2))

    # --- kullanıcılar ---
    users: list[models.User] = []
    for i, p in enumerate(PEOPLE):
        users.append(
            models.User(
                email=f"demo{i + 1}@{DEMO_DOMAIN}",
                password_hash=_hash_password("Demo1234!"),
                verified=True,
                name=p["name"],
                gender=p["gender"],
                birth_year=p["birth_year"],
                university=p["university"],
                department=p["department"],
                year=p["year"],
                budget_min=p["budget"][0],
                budget_max=p["budget"][1],
                smoking=p["smoking"],
                alcohol=p["alcohol"],
                pets=p["pets"],
                sleep_schedule=p["sleep"],
                preferred_districts=p["districts"],
                bio=p["bio"],
                photos=[p["photo"]],
            )
        )
    db.add_all(users)
    db.flush()

    # --- ilanlar ---
    for item in LISTINGS:
        owner = users[item["owner"]]
        rent = median_rent(item["district"], item["neighborhood"], item["rooms"])
        common = dict(
            owner_id=owner.id,
            type=item["type"],
            title=item["title"],
            description=item["description"],
            district=item["district"],
            # Mahalle kaydedilir: adil fiyat böylece ilçe geneli yerine
            # mahalle bazında çalışır (bkz. app/fairprice.py).
            neighborhood=item["neighborhood"],
            photos=[_unsplash(p) for p in item["photos"]],
        )
        if item["type"] == "ev_ilani":
            listing = models.Listing(
                **common,
                rent=rent,
                room_count=item["rooms"],
                smoking_allowed=item["smoking"],
                pets_allowed=item["pets"],
            )
        else:
            listing = models.Listing(
                **common,
                budget_min=owner.budget_min,
                budget_max=owner.budget_max,
            )
        db.add(listing)

    db.commit()
    print(f"✅ {len(users)} demo kullanıcı + {len(LISTINGS)} özenli ilan eklendi "
          f"(kiralar TÜFE x{factor:.4f} ile endeksli).")
    db.close()


if __name__ == "__main__":
    seed(force="--force" in sys.argv)
