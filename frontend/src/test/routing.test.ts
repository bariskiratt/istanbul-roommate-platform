/**
 * App.tsx'teki her rotanın vercel.json'da bir rewrite'ı olmalı.
 *
 * Neden: Vercel statik dosya sunuyor. "/privacy" adresine doğrudan girildiğinde
 * (yer imi, paylaşılan bağlantı, Google sonucu) o adla bir dosya olmadığı için
 * rewrite yoksa 404 döner — uygulama içinden tıklayarak gidince ÇALIŞIR, çünkü
 * yönlendirmeyi tarayıcıdaki router yapar. Yani hata yalnızca dışarıdan gelen
 * ziyaretçide görünür ve geliştirirken fark edilmez.
 *
 * Bu tam olarak üretimde iki kez yaşandı: bir kez catch-all rewrite'ı açık
 * rotalarla değiştirirken, bir kez de cleanUrls bütün rewrite hedeflerini
 * bozarken. İkisi de elle yakalandı.
 */

// Vitest 4 Node tiplerini artık kendiliğinden getirmiyor; bu test dosyaları
// diskten okuduğu için tipler buradan eklenir.
/// <reference types="node" />
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { INDEXABLE_ROUTES } from "../lib/routeMeta";

const root = join(__dirname, "../..");

function appRoutes(): string[] {
  const src = readFileSync(join(root, "src/App.tsx"), "utf8");
  return [...src.matchAll(/<Route\s+path="([^"]+)"/g)]
    .map(m => m[1])
    .filter(p => p !== "*" && p !== "/");
}

function vercelRewrites(): { source: string; destination: string }[] {
  return JSON.parse(readFileSync(join(root, "vercel.json"), "utf8")).rewrites;
}

describe("rota yönlendirmeleri", () => {
  it("her uygulama rotasının bir rewrite'ı var", () => {
    const sources = new Set(vercelRewrites().map(r => r.source));
    const eksik = appRoutes().filter(p => !sources.has(p));
    expect(eksik, "vercel.json'a eklenmemiş rota").toEqual([]);
  });

  it("uygulama rewrite'ları index.html'e gidiyor", () => {
    // Arama motoruna açık rotalar derlemede kendi kopyasını alır
    // (scripts/route-heads.ts), gerisi ortak index.html'i.
    const routes = new Set(appRoutes());
    const indexable = new Set<string>(INDEXABLE_ROUTES);
    for (const r of vercelRewrites()) {
      if (!routes.has(r.source)) continue;
      expect(r.destination, `${r.source} yanlış hedefe gidiyor`).toBe(
        indexable.has(r.source) ? `${r.source}/index.html` : "/index.html",
      );
    }
  });

  it("cleanUrls kapalı", () => {
    // Açıkken Vercel /index.html -> / yönlendirmesi yapıyor ve bu, YUKARIDAKİ
    // her rewrite'ın hedefi olduğu için uygulamanın tamamını 404'e düşürüyor.
    const cfg = JSON.parse(readFileSync(join(root, "vercel.json"), "utf8"));
    expect(cfg.cleanUrls).toBeUndefined();
  });
});
