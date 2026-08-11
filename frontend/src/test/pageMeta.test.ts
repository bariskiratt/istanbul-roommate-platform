/**
 * Her rotanın kendi sekme başlığını aldığını doğrular.
 *
 * Asıl korunan şey: App.tsx'e yeni bir rota eklenip PageMeta'daki tabloya
 * eklenmezse sayfa sessizce "Sayfa bulunamadı" başlığıyla gezer. Aşağıdaki
 * ilk test o durumu görünür kılıyor.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { matchRoute } from "../components/PageMeta";
import { translations } from "../i18n/translations";

const { tr, en } = translations;

/** App.tsx'teki <Route path="..."> değerlerini okur. */
function appRoutes(): string[] {
  const src = readFileSync(join(__dirname, "../App.tsx"), "utf8");
  return [...src.matchAll(/<Route\s+path="([^"]+)"/g)]
    .map(m => m[1])
    .filter(p => p !== "*"); // yakalama rotası zaten NotFound
}

describe("PageMeta", () => {
  it("App.tsx'teki her rotanın bir başlığı var", () => {
    const eksik = appRoutes().filter(
      p => matchRoute(p).title === "meta.notFound",
    );
    expect(eksik).toEqual([]);
  });

  it("dinamik segmentli rotayı eşler", () => {
    expect(matchRoute("/chat/42").title).toBe("meta.chat");
    expect(matchRoute("/chat/abc-123").title).toBe("meta.chat");
  });

  it("segment sayısı tutmayan yolu eşlemez", () => {
    expect(matchRoute("/chat").title).toBe("meta.notFound");
    expect(matchRoute("/chat/42/fazladan").title).toBe("meta.notFound");
  });

  it("bilinmeyen yol NotFound başlığı alır", () => {
    expect(matchRoute("/boyle-bir-sayfa-yok").title).toBe("meta.notFound");
  });

  it("robots.txt'de açık olan rotaların açıklaması da var", () => {
    // Bunlar arama sonucuna çıkıyor; açıklamasız kalırlarsa Google
    // sayfadan rastgele bir cümle seçer.
    for (const p of ["/", "/onboarding", "/login", "/explore", "/safety"]) {
      expect(matchRoute(p).desc, `${p} açıklamasız`).toBeDefined();
    }
  });

  it("kullanılan bütün anahtarlar iki sözlükte de var", () => {
    for (const p of [...appRoutes(), "/bilinmeyen"]) {
      const { title, desc } = matchRoute(p);
      expect(tr[title], `tr: ${title}`).toBeTruthy();
      expect(en[title], `en: ${title}`).toBeTruthy();
      if (desc) {
        expect(tr[desc], `tr: ${desc}`).toBeTruthy();
        expect(en[desc], `en: ${desc}`).toBeTruthy();
      }
    }
  });
});
