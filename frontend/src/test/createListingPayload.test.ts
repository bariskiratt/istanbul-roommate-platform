import { describe, it, expect } from "vitest";
import { buildListingPayload, type ListingDraft } from "@/pages/CreateListing";
import { LISTING_FEATURES, type ListingFeature } from "@/lib/api";

const noFeatures = (): Record<ListingFeature, boolean> =>
  Object.fromEntries(LISTING_FEATURES.map(k => [k, false])) as Record<ListingFeature, boolean>;

const draft = (over: Partial<ListingDraft> = {}): ListingDraft => ({
  listingType: "ev_ilani",
  title: "Kadıköy'de oda",
  description: "Ferah, aydınlık.",
  location: { district: "Kadıköy", neighborhood: "" },
  photos: ["a.jpg", "b.jpg", "c.jpg"],
  rent: "9000",
  roomCount: "2+1",
  smokingAllowed: false,
  petsAllowed: true,
  features: noFeatures(),
  budget: [4000, 8000],
  ...over,
});

describe("buildListingPayload", () => {
  it("ev ilanında seçilen mahalleyi gönderir", () => {
    const p = buildListingPayload(
      draft({ location: { district: "Kadıköy", neighborhood: "Caferağa Mah." } }),
    );
    expect(p.neighborhood).toBe("Caferağa Mah.");
    expect(p.district).toBe("Kadıköy");
  });

  it("mahalle seçilmediyse alanı hiç yollamaz (boş dize göndermez)", () => {
    const p = buildListingPayload(draft());
    expect("neighborhood" in p).toBe(false);
  });

  it("kişisel ilanda mahalle GÖNDERİLMEZ — kullanıcı ev ilanında seçip tipi değiştirmiş olsa bile", () => {
    // Adımlar arasında geri gidip ilan tipini değiştirmek form durumunu korur;
    // artık gösterilmeyen mahalle sessizce kaydedilmemeli.
    const p = buildListingPayload(
      draft({
        listingType: "kisisel_ilan",
        location: { district: "Kadıköy", neighborhood: "Caferağa Mah." },
      }),
    );
    expect("neighborhood" in p).toBe(false);
    expect(p.district).toBe("Kadıköy");
  });

  it("kişisel ilanda ev alanları gönderilmez, bütçe gönderilir", () => {
    const p = buildListingPayload(draft({ listingType: "kisisel_ilan", budget: [5000, 9000] }));
    expect(p.budget_min).toBe(5000);
    expect(p.budget_max).toBe(9000);
    expect(p.rent).toBeUndefined();
    expect(p.room_count).toBeUndefined();
    for (const key of LISTING_FEATURES) expect(p[key]).toBeUndefined();
  });

  it("ev ilanında 7 özelliğin hepsi açıkça yazılır (işaretsizler false)", () => {
    const features = { ...noFeatures(), furnished: true, balcony: true };
    const p = buildListingPayload(draft({ features }));
    expect(p.furnished).toBe(true);
    expect(p.balcony).toBe(true);
    for (const key of LISTING_FEATURES) expect(typeof p[key]).toBe("boolean");
    expect(p.elevator).toBe(false);
    expect(p.budget_min).toBeUndefined();
  });

  it("kira metni sayıya çevrilir", () => {
    expect(buildListingPayload(draft({ rent: "12500" })).rent).toBe(12500);
  });
});
