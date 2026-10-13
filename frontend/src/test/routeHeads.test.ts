/**
 * Arama motoruna açık rotaların kendi <head>'i (scripts/route-heads.ts).
 *
 * Korunan hata: her rota ana sayfanın canonical'ını taşıyordu ve Google
 * /explore, /safety, /privacy'yi ana sayfanın kopyası sayıyordu. Ayrıca açık
 * bir rota sitemap'e ya da robots.txt'ye yansımadan eklenirse burada görünür.
 */

// Vitest 4 Node tiplerini kendiliğinden getirmiyor; bu dosya diskten okuyor.
/// <reference types="node" />
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { withRouteHead } from "../../scripts/route-heads";
import { translations } from "../i18n/translations";
import { INDEXABLE_ROUTES } from "../lib/routeMeta";

const root = join(__dirname, "../..");
const html = readFileSync(join(root, "index.html"), "utf8");

const attr = (out: string, re: RegExp) => out.match(re)?.[1];

describe("rotaya özel head", () => {
  it("her açık rota kendi adresini canonical ve og:url olarak verir", () => {
    for (const route of INDEXABLE_ROUTES) {
      const out = withRouteHead(html, route);
      const url = route === "/" ? "https://evdes.tr/" : `https://evdes.tr${route}`;
      expect(attr(out, /<link rel="canonical" href="([^"]*)"/), route).toBe(url);
      expect(attr(out, /<meta property="og:url" content="([^"]*)"/), route).toBe(url);
    }
  });

  it("başlık ve açıklama Türkçe sözlükten gelir", () => {
    const out = withRouteHead(html, "/explore");
    expect(attr(out, /<title>([^<]*)<\/title>/)).toBe(`${translations.tr["meta.explore"]} — evdes.tr`);
    expect(attr(out, /<meta name="description" content="([^"]*)"/)).toBe(
      translations.tr["meta.exploreDesc"],
    );
    // Ana sayfa başlığı markayı zaten içeriyor, tekrar eklenmez.
    expect(attr(withRouteHead(html, "/"), /<title>([^<]*)<\/title>/)).toBe(
      translations.tr["meta.home"],
    );
  });

  it("index.html'deki ana sayfa metinleri sözlükle aynı", () => {
    // Geliştirme sunucusu index.html'i olduğu gibi verir; derleme ise
    // sözlükten yeniden yazar. İkisi ayrışmasın.
    expect(withRouteHead(html, "/")).toBe(html);
  });

  it("etiket bulunamazsa derlemeyi durdurur", () => {
    const eksik = html.replace(/<link rel="canonical"[^>]*>/, "");
    expect(() => withRouteHead(eksik, "/explore")).toThrow(/canonical/);
  });

  it("açık rotalar robots.txt'de kapalı değil, giriş dışındakiler sitemap'te", () => {
    const robots = readFileSync(join(root, "public/robots.txt"), "utf8");
    const kapali = [...robots.matchAll(/^Disallow:\s*(\S+)/gm)].map(m => m[1]);
    const sitemap = readFileSync(join(root, "scripts/generate-seo.mjs"), "utf8");
    for (const route of INDEXABLE_ROUTES) {
      expect(kapali.some(k => route.startsWith(k)), `${route} robots.txt'de kapalı`).toBe(false);
      if (route === "/" || route === "/login") continue;
      expect(sitemap, `${route} sitemap'te yok`).toContain(`{ loc: \`\${SITE}${route}\``);
    }
  });
});
