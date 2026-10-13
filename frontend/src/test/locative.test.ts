/**
 * Semt sayfalarındaki bulunma eki (scripts/locative.mjs).
 *
 * Ek elle "'de" yazılıyordu; 38 semtin 17'sinin başlığı yanlış Türkçeydi
 * ("Adalar'de", "Beşiktaş'de", "Beyoğlu'de").
 */

import { describe, expect, it } from "vitest";

// .mjs betiğinin tip bildirimi yok; bkz. seo-slug.test.ts.
import { locative } from "../../scripts/locative.mjs";

describe("bulunma eki", () => {
  it("son ünlüye uyar", () => {
    expect(locative("Kadıköy")).toBe("Kadıköy'de");
    expect(locative("Adalar")).toBe("Adalar'da");
    expect(locative("Üsküdar")).toBe("Üsküdar'da");
    expect(locative("Tuzla")).toBe("Tuzla'da");
    expect(locative("Şişli")).toBe("Şişli'de");
  });

  it("sert ünsüzden sonra t olur", () => {
    expect(locative("Beşiktaş")).toBe("Beşiktaş'ta");
    expect(locative("Fatih")).toBe("Fatih'te");
    expect(locative("Pendik")).toBe("Pendik'te");
    expect(locative("Esenyurt")).toBe("Esenyurt'ta");
  });

  it("tamlama ekiyle biten adlar n alır", () => {
    expect(locative("Beyoğlu")).toBe("Beyoğlu'nda");
    expect(locative("Zeytinburnu")).toBe("Zeytinburnu'nda");
    expect(locative("Beylikdüzü")).toBe("Beylikdüzü'nde");
  });
});
