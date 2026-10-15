"""İstemediklerim: kişinin ev arkadaşında kesinlikle istemediği özellikler.

Kayıtta (ve profil düzenlemede) sorulur: "sigara içen", "gece kuşu" … Hinge'deki
"dealbreaker" gibi KESİN bir elemedir; seçilen özelliği taşıyan kişinin ilanı
listelerde sona itilmez, hiç gelmez. Kural iki yönlüdür:

1. Benim elediğim kişilerin ilanlarını görmem; beğenileri de Beğeniler
   kuyruğuma düşmez (swipes.received_likes).
2. Beni eleyen kişinin ilanını da görmem. Görseydim, beğenim karşı tarafın
   hiç görmeyeceği bir kuyruğa düşer ve cevapsız kalırdı.

YALNIZCA KARTTA ZATEN GÖRÜNEN ALANLARA BAKILIR: ilan sahibinin sigara, alkol,
evcil hayvan cevabı ve uyku düzeni (models.Listing.owner_profile) ile ev
ilanının kuralları. Bütçe, semtler, bio, cinsiyet ve yaş destede bilerek gizli;
onlara dayanan bir eleme, kimin göründüğüne bakarak gizli alanı okutturabilirdi.

Bilinmeyen (NULL) cevap eleme sebebi DEĞİLDİR: elenen yalnızca açıkça "evet"
diyendir. Hiç seçim yapmamış kişi için hiçbir şey değişmez.

Kişinin kendi seçimleri yalnızca kendisine döner (auth.UserOut). Başkasına
giden hiçbir yanıtta yoktur (swipes.UserPublic, Listing.owner_profile).
"""

from typing import Literal, get_args

from app import models

Dealbreaker = Literal["smoking", "alcohol", "pets", "night_owl", "early_bird"]
DEALBREAKERS: tuple[str, ...] = get_args(Dealbreaker)


def chosen(user: models.User | None) -> list[str]:
    """Kişinin geçerli seçimleri (bilinmeyen ya da eski anahtar sayılmaz)."""
    if user is None:
        return []
    return [key for key in (user.dealbreakers or []) if key in DEALBREAKERS]


def person_has(person: models.User | None, key: str) -> bool:
    """Kişi bu özelliği açıkça taşıyor mu? Cevap yoksa hayır."""
    if person is None:
        return False
    if key == "smoking":
        return person.smoking is True
    if key == "alcohol":
        return person.alcohol is True
    if key == "pets":
        return person.pets is True
    if key == "night_owl":
        return person.sleep_schedule == "gece"
    if key == "early_bird":
        return person.sleep_schedule == "erken"
    return False


def listing_has(listing: models.Listing, key: str) -> bool:
    """İlan bu özelliği taşıyor mu: sahibinin kendisi ya da evin kuralı.

    Ev ilanında "sigara içilebilir" ya da "evcil hayvan kabul edilir" diyen
    ev de elenir: sigara istemeyen kişi, sahibi içmese de sigara içilen eve
    taşınmak istemez.
    """
    if person_has(listing.owner, key):
        return True
    if listing.type == "ev_ilani":
        if key == "smoking":
            return listing.smoking_allowed is True
        if key == "pets":
            return listing.pets_allowed is True
    return False


def hides_listing(viewer: models.User, listing: models.Listing) -> bool:
    """İlan bu kullanıcıya gösterilmemeli mi (iki yönlü kural)?"""
    if any(listing_has(listing, key) for key in chosen(viewer)):
        return True
    return any(person_has(viewer, key) for key in chosen(listing.owner))


def hides_person(viewer: models.User, person: models.User | None) -> bool:
    """Kişi, bu kullanıcının elediği bir özelliği taşıyor mu?"""
    return any(person_has(person, key) for key in chosen(viewer))
