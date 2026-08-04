/**
 * Semt URL'lerinin regresyon testi.
 *
 * Üretimde beş semdin adresi baş harfini kaybetmişti (/semt/skudar). Adresler
 * bir kez indekslenince değiştirmek yönlendirme + yeniden tarama demek, o
 * yüzden bu davranış teste bağlandı.
 */

import { describe, expect, it } from "vitest";

// @ts-expect-error - .mjs betiğinin tip bildirimi yok
import { slug, slugDropsCharacters } from "../../scripts/slug.mjs";

describe("semt slug", () => {
  it("baş harfi Türkçe olan semtlerde o harfi korur", () => {
    // Hatanın tam olarak bozduğu beş ad.
    expect(slug("Şişli")).toBe("sisli");
    expect(slug("Üsküdar")).toBe("uskudar");
    expect(slug("Ümraniye")).toBe("umraniye");
    expect(slug("Çekmeköy")).toBe("cekmekoy");
    expect(slug("Şile")).toBe("sile");
  });

  it("kelime içindeki Türkçe harfleri çevirmeye devam eder", () => {
    expect(slug("Kadıköy")).toBe("kadikoy");
    expect(slug("Bağcılar")).toBe("bagcilar");
    expect(slug("Gaziosmanpaşa")).toBe("gaziosmanpasa");
    expect(slug("Büyükçekmece")).toBe("buyukcekmece");
    expect(slug("Eyüpsultan")).toBe("eyupsultan");
  });

  it("boşlukları tireye çevirir, uçlardaki tireyi kırpar", () => {
    expect(slug("  Küçük Çekmece  ")).toBe("kucuk-cekmece");
  });

  it("düşen karakteri raporlar", () => {
    expect(slugDropsCharacters("Üsküdar")).toBe(false);
    expect(slugDropsCharacters("Kadıköy")).toBe(false);
    // Eşlemede olmayan bir harf sessizce düşerdi; nöbetçi bunu görmeli.
    expect(slugDropsCharacters("Ñoño")).toBe(true);
  });
});
