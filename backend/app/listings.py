"""İlan CRUD uçları.

İlan oluşturma ve güncelleme giriş ister; metinler yayına girmeden önce
içerik denetiminden (app.moderation) geçer.
"""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from sqlalchemy.orm import joinedload

from app import content_limits, models, moderation
from app.auth import get_current_user, get_optional_user
from app.db import get_db
from app.uploads import (
    MAX_PHOTO_URL_LENGTH,
    delete_local_photos,
    is_allowed_photo_url,
    local_photo_name,
)

router = APIRouter(prefix="/api/listings", tags=["listings"])

ListingType = Literal["ev_ilani", "kisisel_ilan"]

# Ev özellikleri — şemalar ve "features" filtresi aynı listeden beslenir ki
# yeni bir özellik eklenince filtre kendiliğinden tanısın.
FEATURE_FIELDS: tuple[str, ...] = (
    "furnished",
    "elevator",
    "parking",
    "internet_included",
    "heating_included",
    "balcony",
    "natural_gas",
)


# Denetim reddinde hangi alanın sorunlu olduğu arayüze bu adlarla bildirilir.
_FIELD_LABELS = {"title": "Başlıkta", "description": "Açıklamada"}


def _check_photos(value: list[str] | None) -> list[str] | None:
    """Fotoğraf listesindeki HER ÖĞEYİ tek tek doğrular.

    Eskiden yalnızca öğe SAYISI sınırlıydı (min 3, en fazla 6); öğenin kendisi
    istenen uzunlukta, istenen içerikte bir dizeydi. 2 MB'lık altı "data:"
    dizesiyle açılan bir ilan hem satırı hem de anonim liste ucunun yanıtını
    megabaytlara çıkarıyordu (bulgu H2). Ayrıca adres serbest olduğu için
    ilan fotoğrafı saldırganın sunucusundan çekilebiliyordu.

    Kural: her öğe en fazla MAX_PHOTO_URL_LENGTH karakter VE
    uploads.is_allowed_photo_url'den geçmeli (kendi yüklemelerimiz + kapalı
    listedeki barındırıcılar).
    """
    if value is None:
        return value
    for url in value:
        if not isinstance(url, str) or not url.strip():
            raise ValueError("Fotoğraf adresi boş olamaz.")
        if len(url) > MAX_PHOTO_URL_LENGTH:
            raise ValueError(
                f"Fotoğraf adresi {MAX_PHOTO_URL_LENGTH} karakterden uzun olamaz."
            )
        if not is_allowed_photo_url(url):
            raise ValueError(
                "Fotoğraf adresi kabul edilmiyor: yalnızca uygulamaya "
                "yüklenen fotoğraflar ve izin verilen barındırıcılar geçerli."
            )
    return value


def _reject(field: str, reasons: list[str]) -> HTTPException:
    """Alanı adıyla anan, yapılandırılmış 422 üretir.

    detail bir SÖZLÜKTÜR: arayüz `field` ile hatalı girdiyi işaretleyip
    kullanıcıyı doğru adıma götürebilsin diye. Metin sabit sözlükten gelir —
    KULLANICI GİRDİSİ hata mesajına asla yansıtılmaz.
    """
    label = _FIELD_LABELS.get(field, "Metinde")
    return HTTPException(
        status_code=422,
        detail={
            # describe() özneyi kendisi kurar; cümleyi elle kırpmak Türkçe'de
            # büyük İ'nin küçük harfe çevrilmesinde bozuk çıktı veriyor.
            "message": (
                f"{moderation.describe(reasons, subject=label)} "
                "Bu alanı düzenleyip tekrar deneyin."
            ),
            "field": field,
            "reasons": reasons,
        },
    )


def _moderate_field(text: str, field: str) -> moderation.ModerationResult:
    """Tek bir alanı denetler; engellenirse alanı adıyla anan 422 fırlatır."""
    # Kullanıcı sistemin ağzından konuşamaz: yönetici kuyruğunda ilan metni
    # olduğu gibi gösterildiği için sistem sabitleri yasak
    # (bkz. moderation.SYSTEM_MARKERS).
    if moderation.is_system_marker(text):
        raise HTTPException(
            status_code=422,
            detail={
                "message": moderation.SYSTEM_MARKER_REJECTION,
                "field": field,
                "reasons": [moderation.SYSTEM_MARKER],
            },
        )

    result = moderation.check(text, kind="listing")
    if result.blocked:
        raise _reject(field, result.reasons)
    return result


def _moderate(title: str, description: str) -> moderation.ModerationResult:
    """Başlığı ve açıklamayı AYRI AYRI denetler, sonuçları birleştirir.

    Ayrı denetlenmesinin tek sebebi geri bildirim: ikisi birleştirilip tek
    metin olarak denetlendiğinde kullanıcı hangi alanı düzelteceğini
    bilemiyordu. Kayıt üzerindeki işaret ve gerekçeler için sonuçlar yine
    tek bir sonuca indirgenir (moderation.merge).
    """
    return moderation.merge(
        _moderate_field(title, "title"),
        _moderate_field(description, "description"),
    )


def moderate_listing_text(
    title: str, description: str
) -> moderation.ModerationResult:
    """Başlığı ve açıklamayı denetler ama HİÇBİR ŞEYİ ENGELLEMEZ.

    _moderate ile aynı metni aynı kurallardan geçirir; tek farkı, "block"
    sonucunda 422 fırlatmak yerine sonucu olduğu gibi döndürmesidir. Yönetici
    düzenlemesi (PATCH /api/admin/listings/{id}) bunu kullanır: moderasyonun
    yöneticiyi durdurması, kaldırılamayan bir ilanı düzeltmek için gelen
    yöneticiyi tam da düzeltmek istediği metin yüzünden dışarıda bırakırdı.
    Denetim yine de ÇALIŞIR; sonucu kayda işaret olarak yazılır, böylece
    yöneticinin bıraktığı metin de inceleme kuyruğunda görünür.
    """
    return moderation.merge(
        moderation.check(title, kind="listing"),
        moderation.check(description, kind="listing"),
    )


def flag_state(result: moderation.ModerationResult) -> tuple[bool, str | None]:
    """Denetim sonucunu kayda yazılacak (işaretli mi, gerekçe CSV) çiftine çevirir.

    moderation.reasons_csv "block" sonucunda None döner ve bu KULLANICI yolu
    için doğrudur: engellenen metin zaten kaydedilmiyor, gerekçeyi saklayacak
    bir satır yok. Yönetici yolunda ise metin KAYDEDİLİYOR (denetim yöneticiyi
    engellemiyor); orada aynı kuralı uygulamak "işaretli ama sebebi boş" bir
    kayıt üretirdi ve yönetici kuyruğunda neye baktığını kimse anlayamazdı.

    Bu yüzden burada "block" da "flag" da işaret sayılır ve gerekçe korunur.
    """
    flagged = result.flagged or result.blocked
    if not flagged or not result.reasons:
        return flagged, None
    return True, ",".join(result.reasons)


def _photos_in_use_elsewhere(db: Session, listing_id: int) -> set[str]:
    """Başka kayıtların kullandığı yerel fotoğraf DOSYA ADLARI.

    Aynı dosya birden fazla yerde geçebilir: kullanıcı fotoğrafını hem
    profiline hem ilanına koyabilir ya da iki ilanında aynı görseli
    kullanabilir. Silinen ilan yüzünden hâlâ kullanılan bir dosyayı silmek
    başka bir ilanı kırık görselle bırakırdı.

    Karşılaştırma DOSYA ADI üzerinden yapılır, URL metni üzerinden değil:
    aynı dosya bir kayıtta göreli ("/uploads/ab..jpg"), diğerinde mutlak
    adresle durabilir.
    """
    used: set[str] = set()
    others = db.scalars(
        select(models.Listing.photos).where(models.Listing.id != listing_id)
    ).all()
    for photos in others:
        for url in photos or []:
            name = local_photo_name(url) if isinstance(url, str) else None
            if name:
                used.add(name)
    for photos in db.scalars(select(models.User.photos)).all():
        for url in photos or []:
            name = local_photo_name(url) if isinstance(url, str) else None
            if name:
                used.add(name)
    return used


def purge_listing(db: Session, row: models.Listing) -> dict[str, int]:
    """İlanı KALICI siler ve ona bağlı kayıtları temizler. COMMIT ETMEZ.

    Bağlı kayıtlarda iki farklı karar var; ikisi de bilinçli:

    1. SİLİNİR — o ilana verilmiş kaydırmalar (swipes) ve hedefi bu ilan olan
       raporlar. İkisi de yalnızca ilan var olduğu sürece anlamlı: konusu
       kalmamış bir rapor yönetici kuyruğunda tıklanınca 404 veren ölü kayıt
       olurdu.
    2. YAŞAR — eşleşmeler ve sohbetler. matches.listing_id NULL'a çekilir,
       satır durur. İlan bir eşleşmenin BAŞLAMA SEBEBİDİR, konusu değil:
       ilanı silmek insanların birbirine yazdıklarını silmez. models.Match
       zaten bunu öngörüp listing_id'yi nullable tanımlamış ("ilan kapansa da
       eşleşme yaşar").

    Postgres'te bu temizlik ZORUNLUDUR: swipes.listing_id ve matches.listing_id
    yabancı anahtar kısıtı taşır, atlanırsa DELETE reddedilir ve uç 500 verir.
    (SQLite'ta kısıtlar varsayılan kapalı olduğu için hata testte değil
    üretimde görünürdü.)

    FOTOĞRAF DOSYALARI da silinir (bulgu H6): satır gidip dosya kalırsa
    /uploads/<ad> adresi girişsiz ve süresiz erişilebilir olmaya devam eder.
    Yalnızca BİZİM ürettiğimiz ve BAŞKA HİÇBİR kayıtta kullanılmayan dosyalar
    silinir. Dosya silme geri alınamaz; çağıran taraf işlemi geri sararsa
    (rollback) satır geri gelir ama görseller gelmez — bu uç zaten "kalıcı
    silme" ucudur, çağrıldığı yerde commit ediliyor.
    """
    lid = row.id
    swipes = db.query(models.Swipe).filter(
        models.Swipe.listing_id == lid
    ).delete(synchronize_session=False)
    reports = db.query(models.Report).filter(
        models.Report.target_type == "listing",
        models.Report.target_id == lid,
    ).delete(synchronize_session=False)
    matches = db.query(models.Match).filter(
        models.Match.listing_id == lid
    ).update({models.Match.listing_id: None}, synchronize_session=False)

    photos = list(row.photos or [])
    db.delete(row)
    db.flush()

    in_use = _photos_in_use_elsewhere(db, lid)
    orphans = [
        url
        for url in photos
        if isinstance(url, str) and (local_photo_name(url) or "") not in in_use
    ]
    deleted_photos = delete_local_photos(orphans)

    return {
        "swipes": swipes,
        "reports": reports,
        "detached_matches": matches,
        "photos": deleted_photos,
    }


def _suspended_user_ids():
    """Askıdaki kullanıcıların id'lerini veren alt sorgu."""
    return select(models.User.id).where(models.User.is_suspended.is_(True))


def _exclude_suspended_owners(stmt):
    """Askıdaki sahibin ilanlarını sorgudan eler.

    is_active'e DOKUNULMAZ: askı kalkınca ilanlar kendiliğinden geri gelir.
    owner_id NULL olan (auth öncesi anonim) ilanlar elenmemeli; SQL'de
    "NULL NOT IN (...)" NULL verdiği için açık OR şart.
    """
    return stmt.where(
        models.Listing.owner_id.is_(None)
        | models.Listing.owner_id.not_in(_suspended_user_ids())
    )


def _owner_suspended(row: models.Listing) -> bool:
    return row.owner is not None and bool(row.owner.is_suspended)


def _parse_features(raw: str | None) -> list[str]:
    """"features" sorgu parametresini ayrıştırır; geçersiz anahtarda 422 verir."""
    if not raw or not raw.strip():
        return []
    keys = [part.strip() for part in raw.split(",") if part.strip()]
    invalid = [k for k in keys if k not in FEATURE_FIELDS]
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Geçersiz özellik: {', '.join(invalid)}. "
                f"Geçerli anahtarlar: {', '.join(FEATURE_FIELDS)}."
            ),
        )
    # Tekrar eden anahtar aynı koşulu iki kez eklemesin.
    return list(dict.fromkeys(keys))


class ListingIn(BaseModel):
    type: ListingType
    title: str = Field(..., min_length=3, max_length=120)
    description: str = Field(..., min_length=1, max_length=2000)
    district: str = Field(..., min_length=1, max_length=40)
    # Mahalle isteğe bağlı: verilirse ve model tanıyorsa adil fiyat tahmini
    # mahalle bazında yapılır, yoksa ilçe geneline düşer (bkz. app/fairprice.py).
    neighborhood: str | None = Field(None, max_length=80)
    # En az 3 fotoğraf: tek fotoğraflı ilanlar hem güven vermiyor hem de
    # kaydırma destesinde ayırt edilemiyordu.
    photos: list[str] = Field(..., min_length=3, max_length=6)

    # Ev ilanı alanları
    rent: int | None = Field(None, gt=0, le=10_000_000)
    room_count: str | None = Field(None, max_length=10)
    smoking_allowed: bool | None = None
    pets_allowed: bool | None = None

    # Ev özellikleri — üç durumlu: True = var, False = yok, None = belirtilmemiş.
    furnished: bool | None = None
    elevator: bool | None = None
    parking: bool | None = None
    internet_included: bool | None = None
    heating_included: bool | None = None
    balcony: bool | None = None
    natural_gas: bool | None = None

    # Kişisel ilan alanları
    budget_min: int | None = Field(None, gt=0, le=10_000_000)
    budget_max: int | None = Field(None, gt=0, le=10_000_000)

    @field_validator("photos")
    @classmethod
    def _check_photo_urls(cls, value):
        return _check_photos(value)

    @model_validator(mode="after")
    def _check_type_fields(self):
        if self.type == "ev_ilani":
            if self.rent is None or not self.room_count:
                raise ValueError("Ev ilanı için kira ve oda sayısı zorunlu.")
        else:
            if self.budget_min is None or self.budget_max is None:
                raise ValueError("Kişisel ilan için bütçe aralığı zorunlu.")
            if self.budget_min > self.budget_max:
                raise ValueError("Bütçe alt sınırı üst sınırdan büyük olamaz.")
        return self


# NOT: ListingIn'den türetilmez — türetilirse tip doğrulayıcısı yanıt
# şemasında da koşar ve bozuk bir satır GET'leri 500'e düşürür.
class ListingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: ListingType
    title: str
    description: str
    district: str
    neighborhood: str | None = None
    photos: list[str]
    rent: int | None
    room_count: str | None
    smoking_allowed: bool | None
    pets_allowed: bool | None
    furnished: bool | None = None
    elevator: bool | None = None
    parking: bool | None = None
    internet_included: bool | None = None
    heating_included: bool | None = None
    balcony: bool | None = None
    natural_gas: bool | None = None
    budget_min: int | None
    budget_max: int | None
    is_active: bool
    created_at: datetime
    owner_id: int | None = None
    owner_name: str | None = None
    owner_university: str | None = None


def _hide_owner(row: models.Listing) -> ListingOut:
    """İlanı sahibinin adı ve üniversitesi olmadan döndürür.

    GİRİŞSİZ istemciye ilan sahibinin adı ve okuduğu üniversite gitmemeli:
    ikisi birlikte, hesap bile açmadan tek istekle toplanabilen bir kişi
    listesi üretiyordu (bulgu L3). Bilgi giriş yapan kullanıcıya aynen
    dönmeye devam eder — kimin ilanına baktığını görmek ürünün özü.

    owner_id KALIR: kimliğe götüren bir isim değil, arayüzün "bu benim ilanım"
    ve raporlama akışlarında kullandığı iç anahtar.
    """
    return ListingOut.model_validate(row).model_copy(
        update={"owner_name": None, "owner_university": None}
    )


@router.post("", status_code=201, response_model=ListingOut)
def create_listing(
    payload: ListingIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """İlan oluşturma giriş ister — anonim ilan spam'ine kapalı."""
    # Giriş ŞARTI tek başına yetmiyordu: tek jetonla yüzlerce ilan açılıp
    # deste ve arama sonuçları doldurulabiliyordu (bulgu H3).
    content_limits.check("listing_create", user.id)

    result = _moderate(payload.title, payload.description)
    row = models.Listing(
        **payload.model_dump(),
        owner_id=user.id,
        is_flagged=result.flagged,
        flag_reasons=moderation.reasons_csv(result),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("", response_model=list[ListingOut])
def list_listings(
    listing_type: ListingType | None = Query(None, alias="type"),
    district: str | None = Query(None, max_length=40),
    mine: bool = Query(False, description="Sadece kendi ilanlarım (giriş ister)"),
    unswiped: bool = Query(
        False, description="Daha önce kaydırdıklarımı ve kendi ilanlarımı gizle"
    ),
    features: str | None = Query(
        None,
        description=(
            "Virgülle ayrılmış ev özellikleri; hepsi işaretli olan ilanlar "
            "döner. Geçerli anahtarlar: " + ", ".join(FEATURE_FIELDS)
        ),
    ),
    db: Session = Depends(get_db),
    user: models.User | None = Depends(get_optional_user),
):
    """Aktif ilanlar, en yeni önce."""
    stmt = (
        select(models.Listing)
        .options(joinedload(models.Listing.owner))  # owner_name için N+1 önlemi
        .where(models.Listing.is_active)
        .order_by(models.Listing.created_at.desc(), models.Listing.id.desc())
    )
    # Askıdaki kullanıcının ilanları hiçbir listede görünmez.
    stmt = _exclude_suspended_owners(stmt)
    if mine:
        if user is None:
            raise HTTPException(status_code=401, detail="Giriş yapman gerekiyor.")
        stmt = stmt.where(models.Listing.owner_id == user.id)
    if unswiped and user is not None:
        # Karar verilmiş ilanlar desteye geri gelmesin; kendi ilanları da çıkar
        swiped = select(models.Swipe.listing_id).where(
            models.Swipe.swiper_id == user.id
        )
        stmt = stmt.where(
            models.Listing.id.not_in(swiped),
            (models.Listing.owner_id != user.id) | models.Listing.owner_id.is_(None),
        )
    if listing_type is not None:
        stmt = stmt.where(models.Listing.type == listing_type)
    if district is not None:
        stmt = stmt.where(models.Listing.district == district)
    for key in _parse_features(features):
        # AND mantığı: istenen her özellik açıkça True olmalı; None
        # (belirtilmemiş) eşleşmez — kullanıcı "var" diyene bakıyor.
        # Ancak bu koşul YALNIZCA ev ilanlarına uygulanır: kişisel ilanlarda
        # (ev arayan kişi) asansör/otopark gibi ev özellikleri hiç olamaz,
        # dolayısıyla filtre onları elemek yerine kapsam dışı bırakır.
        stmt = stmt.where(
            (models.Listing.type != "ev_ilani")
            | getattr(models.Listing, key).is_(True)
        )
    rows = db.scalars(stmt).all()
    if user is None:
        return [_hide_owner(row) for row in rows]
    return rows


@router.get("/{listing_id}", response_model=ListingOut)
def get_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    user: models.User | None = Depends(get_optional_user),
):
    row = db.get(models.Listing, listing_id)
    if row is None or not row.is_active or _owner_suspended(row):
        raise HTTPException(status_code=404, detail="İlan bulunamadı.")
    # Liste ucuyla aynı kural: girişsiz istemci sahibin adını/üniversitesini
    # görmez, yoksa tek tek id gezerek aynı listeyi toplamak yeterdi.
    if user is None:
        return _hide_owner(row)
    return row


@router.get("/{listing_id}/fair-price")
def listing_fair_price(listing_id: int, db: Session = Depends(get_db)):
    """İlanın istediği oda payını modelin adil aralığıyla karşılaştırır.

    Ev arkadaşlığı dinamiği: yatak odaları kişiye özel, salon/mutfak/banyo
    ortaktır. Bu yüzden daire kirası yatak odası sayısına bölünür — "2+1"de
    iki kişi, salon kimseye fatura edilmez, ortak alan olarak paylaşılır.
    """
    from app.fairprice import estimate_for_listing  # döngüsel importu önler

    row = db.get(models.Listing, listing_id)
    if row is None or not row.is_active or _owner_suspended(row):
        raise HTTPException(status_code=404, detail="İlan bulunamadı.")
    if row.type != "ev_ilani" or row.rent is None:
        raise HTTPException(
            status_code=400, detail="Yalnızca ev ilanları için hesaplanır."
        )

    result = estimate_for_listing(
        row.district, row.room_count, row.rent, row.neighborhood
    )
    if result is None:
        raise HTTPException(
            status_code=503, detail="Adil fiyat modeli yüklü değil."
        )
    return result


class ListingUpdate(BaseModel):
    """PATCH — yalnızca gönderilen alanlar güncellenir; tip değiştirilemez."""

    title: str | None = Field(None, min_length=3, max_length=120)
    description: str | None = Field(None, min_length=1, max_length=2000)
    district: str | None = Field(None, min_length=1, max_length=40)
    neighborhood: str | None = Field(None, max_length=80)
    # Gönderilmezse dokunulmaz: alt sınırdan önce açılmış ilanlar bu yüzden
    # kilitlenmez, sahibi başlığını düzeltebilir. Gönderilirse kural aynı.
    photos: list[str] | None = Field(None, min_length=3, max_length=6)
    rent: int | None = Field(None, gt=0, le=10_000_000)
    room_count: str | None = Field(None, max_length=10)
    smoking_allowed: bool | None = None
    pets_allowed: bool | None = None
    furnished: bool | None = None
    elevator: bool | None = None
    parking: bool | None = None
    internet_included: bool | None = None
    heating_included: bool | None = None
    balcony: bool | None = None
    natural_gas: bool | None = None
    budget_min: int | None = Field(None, gt=0, le=10_000_000)
    budget_max: int | None = Field(None, gt=0, le=10_000_000)

    @field_validator("photos")
    @classmethod
    def _check_photo_urls(cls, value):
        return _check_photos(value)


@router.patch("/{listing_id}", response_model=ListingOut)
def update_listing(
    listing_id: int,
    payload: ListingUpdate,
    db: Session = Depends(get_db),
    user: models.User | None = Depends(get_optional_user),
):
    """İlan güncelleme — yalnızca ilan sahibi."""
    row = db.get(models.Listing, listing_id)
    if row is None or not row.is_active:
        raise HTTPException(status_code=404, detail="İlan bulunamadı.")
    if row.owner_id is None or user is None or user.id != row.owner_id:
        raise HTTPException(status_code=403, detail="Bu ilan sana ait değil.")

    # null gönderilen alanlar "değiştirme" sayılır — zorunlu alanların
    # PATCH ile boşaltılıp kaydın bozulmasını engeller.
    updates = {
        k: v
        for k, v in payload.model_dump(exclude_unset=True).items()
        if v is not None
    }
    eff_min = updates.get("budget_min", row.budget_min)
    eff_max = updates.get("budget_max", row.budget_max)
    if eff_min is not None and eff_max is not None and eff_min > eff_max:
        raise HTTPException(
            status_code=422, detail="Bütçe alt sınırı üst sınırdan büyük olamaz."
        )

    # Denetim YALNIZCA metin gerçekten değişiyorsa çalışır.
    # Aksi hâlde: denetim kuralları ilan yayımlandıktan sonra sıkılaştığında,
    # eski metni bugünün kurallarına takılan bir ilanın sahibi kirasını,
    # fotoğrafını, hiçbir alanını güncelleyemez hâle geliyordu (422 kilidi).
    # Kullanıcı metne dokunmuyorsa yeni kuralı ona geriye dönük uygulamıyoruz;
    # başlık veya açıklama değişirse yeni hâl bir bütün olarak denetlenir.
    new_title = updates.get("title", row.title)
    new_description = updates.get("description", row.description)
    if new_title != row.title or new_description != row.description:
        result = _moderate(new_title, new_description)
        row.is_flagged = result.flagged
        row.flag_reasons = moderation.reasons_csv(result)

    for key, value in updates.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{listing_id}", status_code=204)
def deactivate_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Kalıcı silme yerine pasife çeker (satır ve veriler durur).

    DÜRÜSTLÜK NOTU: satır silinmediği için veri kaybı yoktur, ama sahibinin
    KENDİ ELİYLE yeniden yayına alacağı bir uç hâlâ yok — kapatma kullanıcı
    açısından tek yönlüdür. Yeniden yayına almak bugün YÖNETİCİDEN geçiyor
    (POST /api/admin/listings/{id}/publish); kullanıcının kendi düğmesi
    ayrı bir iştir ve yapılmadı.

    (Yöneticinin kaldırdığı ilan ayrı bir durumdur: moderation_removed=True
    olur ve POST /api/admin/listing/{id}/restore ile geri alınır.)

    Yalnızca ilan sahibi kapatabilir; sahipsiz (eski anonim) kayıtlar API'den
    silinemez, gerekirse veritabanından temizlenir.
    """
    row = db.get(models.Listing, listing_id)
    if row is None or not row.is_active:
        raise HTTPException(status_code=404, detail="İlan bulunamadı.")
    if row.owner_id is None or user.id != row.owner_id:
        raise HTTPException(status_code=403, detail="Bu ilan sana ait değil.")
    row.is_active = False
    db.commit()
