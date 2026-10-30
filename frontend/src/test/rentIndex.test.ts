/**
 * Semt sayfaları kira çarpanını backend/app/indexing.py'den okur
 * (scripts/rent-index.mjs).
 *
 * Bir dönem yalnızca ANCHOR_FACTOR okunuyordu. Aylık satırlar eklenince
 * backend yeni çarpanla, semt sayfaları çıpa çarpanıyla konuşacaktı; ikisi
 * aynı mahalle için farklı kira gösterirdi ve hiçbir test bunu yakalamazdı.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

// .mjs betiğinin tip bildirimi yok; bkz. seo-slug.test.ts.
import { rentIndex } from "../../scripts/rent-index.mjs";

const INDEXING = join(__dirname, "../../../backend/app/indexing.py");

const kaynak = (aylik: string) => `
DATA_PERIOD = "2025-02"
ANCHOR_PERIOD = "2026-02"
ANCHOR_FACTOR = 1.5

MONTHLY_AFTER_ANCHOR: dict[str, float] = {${aylik}}
`;

describe("kira endeksi çarpanı", () => {
  it("çıpayı çıpadan sonraki aylık oranlarla çarpar", () => {
    const r = rentIndex(
      kaynak(`
    "2026-04": 1.0,   # yorum satırı bozmamalı
    "2026-03": 2.0,
    "2025-12": 99.0,
`),
    );

    // backend ile aynı: sıralanır, çıpadan önceki ay yok sayılır.
    expect(r.factor).toBeCloseTo(1.5 * 1.02 * 1.01, 10);
    expect(r.indexedTo).toBe("2026-04");
    expect(r.dataPeriod).toBe("2025-02");
  });

  it("aylık tablo boşsa çıpada kalır", () => {
    const r = rentIndex(kaynak(""));
    expect(r.factor).toBe(1.5);
    expect(r.indexedTo).toBe("2026-02");
  });

  it("okuyamadığı satırı atlamaz, derlemeyi durdurur", () => {
    expect(() => rentIndex(kaynak(`\n    "2026-03": 2,2,\n`))).toThrow();
  });

  it("gerçek indexing.py okunabiliyor", () => {
    const src = readFileSync(INDEXING, "utf8");
    const r = rentIndex(src);
    const tablo = src.match(/^MONTHLY_AFTER_ANCHOR[^=]*=\s*\{([^}]*)\}/m)?.[1] ?? "";
    const aylar = [...tablo.matchAll(/"(\d{4}-\d{2})"\s*:/g)].map(m => m[1]).sort();

    // Tablonun son ayına kadar çarpılmış olmalı: hiçbir satır atlanmadı.
    expect(aylar.length).toBeGreaterThan(0);
    expect(r.indexedTo).toBe(aylar[aylar.length - 1]);
    expect(r.factor).toBeGreaterThan(1);
  });
});
