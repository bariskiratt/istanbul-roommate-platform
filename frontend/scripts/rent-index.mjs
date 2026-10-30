/**
 * Kira endeksi çarpanını backend/app/indexing.py kaynağından okur.
 *
 * Ayrı dosyada, çünkü generate-seo.mjs import edilir edilmez tüm siteyi
 * üretiyor; testin yalnızca bu fonksiyona erişebilmesi gerekiyor.
 *
 * backend'deki rent_index() ile AYNI hesabı yapar: çıpa çarpanı, çıpadan
 * sonraki her ayın aylık oranıyla çarpılır. Bir dönem yalnızca
 * ANCHOR_FACTOR okunuyordu; aylık satırlar eklenince semt sayfaları backend'in
 * gerisinde kalıp eski çarpanla konuşacaktı.
 */

/** indexing.py kaynağından {factor, indexedTo, dataPeriod} döndürür. */
export function rentIndex(src) {
  const anchor = src.match(/^ANCHOR_FACTOR\s*=\s*([\d.]+)/m);
  const anchorPeriod = src.match(/^ANCHOR_PERIOD\s*=\s*"(\d{4}-\d{2})"/m);
  const data = src.match(/^DATA_PERIOD\s*=\s*"(\d{4}-\d{2})"/m);
  if (!anchor || !anchorPeriod || !data) {
    throw new Error("indexing.py içinde ANCHOR_FACTOR / ANCHOR_PERIOD / DATA_PERIOD bulunamadı");
  }

  const block = src.match(/^MONTHLY_AFTER_ANCHOR[^=]*=\s*\{([^}]*)\}/m);
  if (!block) throw new Error("indexing.py içinde MONTHLY_AFTER_ANCHOR bulunamadı");

  const months = [];
  for (const raw of block[1].split("\n")) {
    const line = raw.replace(/#.*/, "").trim();
    if (!line) continue;
    const m = line.match(/^"(\d{4}-\d{2})"\s*:\s*(-?[\d.]+)\s*,?$/);
    // Okunamayan satırı atlamak çarpanı sessizce eksik hesaplamak olurdu.
    if (!m) throw new Error(`MONTHLY_AFTER_ANCHOR satırı okunamadı: ${raw.trim()}`);
    months.push([m[1], Number(m[2])]);
  }

  let factor = Number(anchor[1]);
  let indexedTo = anchorPeriod[1];
  for (const [month, pct] of months.sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))) {
    if (month > anchorPeriod[1]) {
      factor *= 1 + pct / 100;
      indexedTo = month;
    }
  }
  return { factor, indexedTo, dataPeriod: data[1] };
}
