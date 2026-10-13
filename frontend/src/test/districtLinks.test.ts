/**
 * Ana sayfadan bağlantı verilen semt sayfaları gerçekten üretiliyor mu.
 *
 * Bağlantı ile sayfa ayrı yerlerde: bağlantı src/lib/districts.ts'te elle,
 * sayfa derlemede CSV'den. Biri değişip öteki kalırsa ana sayfa 404'e
 * bağlantı verir; Google bunu ana sayfada görür.
 */

// Vitest 4 Node tiplerini kendiliğinden getirmiyor; bu dosya diskten okuyor.
/// <reference types="node" />
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

// .mjs betiğinin tip bildirimi yok; bkz. seo-slug.test.ts.
import { slug } from "../../scripts/slug.mjs";
import { LINKED_DISTRICT_PAGES } from "../lib/districts";

const CSV = join(__dirname, "../../../backend/data/processed/neighborhood_market_values.csv");

function generatedSlugs(): Set<string> {
  const [head, ...rows] = readFileSync(CSV, "utf8").trim().split("\n");
  const col = head.split(",").indexOf("district");
  return new Set(rows.map(r => slug(r.split(",")[col])).filter(Boolean));
}

describe("ana sayfadaki semt bağlantıları", () => {
  it("slug, sayfayı üreten slug() ile aynı", () => {
    for (const [name, s] of LINKED_DISTRICT_PAGES) expect(slug(name), name).toBe(s);
  });

  it("her bağlantının sayfası derlemede üretiliyor", () => {
    const uretilen = generatedSlugs();
    for (const [name, s] of LINKED_DISTRICT_PAGES) expect(uretilen.has(s), `${name} -> /semt/${s}`).toBe(true);
  });
});
