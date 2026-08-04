/**
 * Semt sayfalarını ve sitemap'i derleme anında üretir.
 *
 * NEDEN: Uygulama bir SPA; sunucudan gelen HTML'de yalnızca boş bir <div> var
 * ve içerik JavaScript çalışınca doluyor. Arama motoru bunu okuyabilir ama
 * gecikmeli ve güvenilmez okur. Buradaki sayfalar saf HTML: JavaScript
 * gerektirmez, anında yüklenir ve başka hiçbir yerde bulunmayan bir veriyi
 * taşır — mahalle bazında kira medyanı.
 *
 * TEK KAYNAK: TÜFE çarpanı backend/app/indexing.py'den OKUNUR, buraya
 * kopyalanmaz. İki yerde ayrı sayı tutmak, birini güncelleyip diğerini
 * unutmak demektir; bu projede aynı hata (harita endekslenmemişti) zaten
 * bir kez yaşandı.
 *
 * Çalıştırma: npm run build öncesi otomatik (package.json "prebuild").
 */

import { readFileSync, writeFileSync, mkdirSync, rmSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, "..", "..");
const CSV = join(REPO, "backend", "data", "processed", "neighborhood_market_values.csv");
const INDEXING = join(REPO, "backend", "app", "indexing.py");
const OUT_DIR = join(HERE, "..", "public", "semt");
const PUBLIC = join(HERE, "..", "public");

const SITE = "https://evdes.tr";
// Bu eşiğin altındaki mahalle "zayıf veri" sayılır — backend/app/heatmap.py
// ile aynı sayı (MIN_LISTINGS). Az ilana dayanan medyan yanıltıcıdır.
const MIN_LISTINGS = 8;

// ---- kaynak veriler -------------------------------------------------------

function indexFactor() {
  // ANCHOR_FACTOR = 1.656  satırını yakalar.
  const src = readFileSync(INDEXING, "utf8");
  const m = src.match(/^ANCHOR_FACTOR\s*=\s*([\d.]+)/m);
  if (!m) throw new Error("indexing.py içinde ANCHOR_FACTOR bulunamadı");
  const period = src.match(/^ANCHOR_PERIOD\s*=\s*"([\d-]+)"/m);
  const data = src.match(/^DATA_PERIOD\s*=\s*"([\d-]+)"/m);
  return {
    factor: Number(m[1]),
    indexedTo: period ? period[1] : "?",
    dataPeriod: data ? data[1] : "?",
  };
}

function readCsv() {
  if (!existsSync(CSV)) {
    // Sessizce boş sayfa üretmektense derlemeyi durdur: eksik veriyle
    // yayına çıkmak, sayfaların var olduğunu sanmamıza yol açar.
    throw new Error(`Veri dosyası yok: ${CSV}`);
  }
  const [head, ...rows] = readFileSync(CSV, "utf8").trim().split("\n");
  const cols = head.split(",");
  return rows.map(line => {
    // Bu CSV'de tırnaklı alan yok; basit ayırma yeterli.
    const parts = line.split(",");
    return Object.fromEntries(cols.map((c, i) => [c, parts[i]]));
  });
}

// ---- yardımcılar ----------------------------------------------------------

const TR_MAP = { ç: "c", ğ: "g", ı: "i", ö: "o", ş: "s", ü: "u", İ: "i", I: "i" };

/** "Kadıköy" -> "kadikoy" (URL için). */
function slug(name) {
  return name
    .trim()
    .replace(/[çğıöşüİI]/g, ch => TR_MAP[ch] ?? ch)
    .toLocaleLowerCase("tr")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

const nf = new Intl.NumberFormat("tr-TR");
const money = v => `${nf.format(Math.round(v))} ₺`;

/**
 * İlan sayısıyla AĞIRLIKLI medyan.
 *
 * Düz medyan her mahalleyi eşit sayardı: 34 ilanlı Osmanağa ile 3 ilanlı
 * Dumlupınar aynı ağırlıkta olurdu. Oysa okuyucunun sorusu "bu ilçedeki
 * tipik ilan ne kadar", "tipik mahalle ne kadar" değil.
 */
function weightedMedian(pairs) {
  const s = [...pairs].sort((a, b) => a.value - b.value);
  const total = s.reduce((t, x) => t + x.weight, 0);
  if (total === 0) return null;
  let acc = 0;
  for (const x of s) {
    acc += x.weight;
    if (acc >= total / 2) return x.value;
  }
  return s[s.length - 1].value;
}

const esc = s =>
  String(s).replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );

// ---- sayfa şablonu --------------------------------------------------------

function layout({ title, description, canonical, jsonLd, body }) {
  return `<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(title)}</title>
<meta name="description" content="${esc(description)}">
<link rel="canonical" href="${canonical}">
<meta property="og:type" content="article">
<meta property="og:title" content="${esc(title)}">
<meta property="og:description" content="${esc(description)}">
<meta property="og:url" content="${canonical}">
<meta property="og:locale" content="tr_TR">
<link rel="icon" href="/favicon.ico">
<script type="application/ld+json">${JSON.stringify(jsonLd)}</script>
<style>
:root{color-scheme:light dark;--fg:#1c1914;--muted:#6b6459;--line:#e5e0d8;--bg:#faf7f2;--accent:#3f2d63}
@media(prefers-color-scheme:dark){:root{--fg:#ece5da;--muted:#a39a8d;--line:#2a2622;--bg:#141210;--accent:#b9a3e8}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
  font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:52rem;margin:0 auto;padding:2.5rem 1.25rem 4rem}
h1{font-size:1.9rem;line-height:1.2;margin:0 0 .5rem}
h2{font-size:1.25rem;margin:2.5rem 0 .75rem}
p{margin:.75rem 0}
a{color:var(--accent)}
.lead{font-size:1.05rem;color:var(--muted)}
.big{font-size:2.1rem;font-weight:700;letter-spacing:-.02em}
table{border-collapse:collapse;width:100%;margin:1rem 0;font-size:.94rem}
th,td{text-align:left;padding:.55rem .5rem;border-bottom:1px solid var(--line)}
th{font-weight:600;color:var(--muted);font-size:.82rem;text-transform:uppercase;letter-spacing:.04em}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.weak td{color:var(--muted)}
.note{font-size:.85rem;color:var(--muted)}
.cta{display:inline-block;margin:1.5rem 0;padding:.8rem 1.4rem;border-radius:999px;
  background:var(--fg);color:var(--bg);text-decoration:none;font-weight:600}
nav.links{margin-top:3rem;padding-top:1.5rem;border-top:1px solid var(--line);
  font-size:.9rem;line-height:2}
footer{margin-top:3rem;padding-top:1.5rem;border-top:1px solid var(--line);
  font-size:.85rem;color:var(--muted)}
</style>
</head>
<body><main>
${body}
<footer>
<p><a href="/">evdes.tr</a> — İstanbul'daki üniversite öğrencileri için ev arkadaşı platformu.
Veriler ${esc(FACTOR.dataPeriod)} dönemine ait ${esc(String(TOTAL_LISTINGS))} ilandan hesaplandı ve
TÜİK konut endeksiyle ${esc(FACTOR.indexedTo)} düzeyine taşındı.</p>
</footer>
</main></body></html>
`;
}

// ---- içerik ---------------------------------------------------------------

const FACTOR = indexFactor();
const rows = readCsv();
let TOTAL_LISTINGS = 0;

const byDistrict = new Map();
for (const r of rows) {
  const district = (r.district ?? "").trim();
  const neighborhood = (r.neighborhood ?? "").trim();
  const price = Number(r.avg_price);
  const count = Number(r.total_listings);
  if (!district || !Number.isFinite(price) || !Number.isFinite(count)) continue;
  TOTAL_LISTINGS += count;
  if (!byDistrict.has(district)) byDistrict.set(district, []);
  byDistrict.get(district).push({
    neighborhood,
    count,
    price: price * FACTOR.factor,   // backend ile aynı çarpan
  });
}

const districts = [...byDistrict.entries()]
  .map(([name, list]) => {
    return {
      name,
      slug: slug(name),
      list: list.sort((a, b) => b.count - a.count),
      listings: list.reduce((s, n) => s + n.count, 0),
      // Ağırlık ilan sayısı olduğu için az ilanlı mahalleler zaten sönük
      // kalır; ayrıca eşikle elemeye gerek yok, veri de boşa gitmez.
      median: weightedMedian(list.map(n => ({ value: n.price, weight: n.count }))),
    };
  })
  .filter(d => d.median != null)
  .sort((a, b) => b.listings - a.listings);

/** Oda payı: yatak odası sayısına bölünür, salon kimseye fatura edilmez. */
const roomShare = flat => flat / 2;   // 2+1 (iki yatak odası) örneği üzerinden

function districtPage(d, others) {
  const url = `${SITE}/semt/${d.slug}`;
  const title = `${d.name} ev arkadaşı ve oda kiraları — evdes.tr`;
  const description =
    `${d.name}'de kiralık daire medyanı ${money(d.median)}, iki yatak odalı bir evde ` +
    `kişi başı yaklaşık ${money(roomShare(d.median))}. ${d.list.length} mahallenin ` +
    `güncel verisi ve ev arkadaşı ilanları.`;

  const satirlar = d.list
    .map(n => {
      const zayif = n.count < MIN_LISTINGS;
      return `<tr${zayif ? ' class="weak"' : ""}>
<td>${esc(n.neighborhood)}</td>
<td class="num">${money(n.price)}</td>
<td class="num">${money(roomShare(n.price))}</td>
<td class="num">${nf.format(n.count)}${zayif ? " *" : ""}</td>
</tr>`;
    })
    .join("\n");

  const komsular = others
    .filter(o => o.slug !== d.slug)
    .slice(0, 12)
    .map(o => `<a href="/semt/${o.slug}">${esc(o.name)}</a>`)
    .join(" · ");

  const body = `
<h1>${esc(d.name)}'de ev arkadaşı ve oda kiraları</h1>
<p class="lead">${esc(d.list.length)} mahalle · ${nf.format(d.listings)} ilan · veriler ${esc(FACTOR.indexedTo)} düzeyinde</p>

<p class="big">${money(roomShare(d.median))}<span style="font-size:1rem;font-weight:400;color:var(--muted)"> / ay kişi başı</span></p>
<p>${esc(d.name)}'de kiralık dairelerin medyan kirası <strong>${money(d.median)}</strong>.
İki yatak odalı bir evi iki kişi paylaştığında kişi başına düşen pay yaklaşık
<strong>${money(roomShare(d.median))}</strong> oluyor.</p>

<h2>Oda payı nasıl hesaplanıyor?</h2>
<p>Ev arkadaşlığında kiralanan şey daire değil, <strong>bir oda</strong>. Salon, mutfak
ve banyo ortak kullanılır, yani kimseye ayrıca fatura edilmez. Bu yüzden pay,
dairenin kirasının <em>yatak odası sayısına</em> bölünmesiyle bulunur: 2+1 bir evde
iki kişi, 3+1'de üç kişi. Yukarıdaki sayı iki yatak odalı bir daire varsayar.</p>

<h2>${esc(d.name)} mahalleleri</h2>
<table>
<thead><tr><th>Mahalle</th><th class="num">Daire kirası</th><th class="num">Oda payı</th><th class="num">İlan</th></tr></thead>
<tbody>
${satirlar}
</tbody>
</table>
<p class="note">* ${MIN_LISTINGS} ilandan az veriye dayanan mahalleler. Medyan bu sayıda
ilanla temsil gücünü kaybeder; sayıyı fikir vermesi için gösteriyoruz, ölçü olarak değil.</p>

<h2>Yöntem</h2>
<p class="note">Her mahallenin rakamı, o mahalledeki ilanların <strong>medyanıdır</strong>
(ortalama değil — birkaç lüks ilan ortalamayı yukarı çeker, medyanı çekmez).
İlçe rakamı ise mahallelerin ilan sayısıyla ağırlıklı medyanıdır, yani çok ilanı
olan bir mahalle sonucu daha çok belirler. Veriler ${esc(FACTOR.dataPeriod)}
dönemine ait ilanlardan gelir ve TÜİK konut endeksiyle bugüne taşınır
(×${FACTOR.factor}); endeksleme enflasyonu izler, semtin kendi hareketini değil.
Bu bir tahmindir, ekspertiz değildir.</p>

<h2>${esc(d.name)}'de ev arkadaşı bul</h2>
<p>evdes.tr üniversite öğrencilerine özel bir ev arkadaşı platformu. Kayıt yalnızca
<strong>.edu.tr</strong> uzantılı okul e-postasıyla yapılır. İlanları kaydırarak
gezersin, karşılıklı beğeni eşleşme yaratır, mesajlaşma eşleşmeden sonra açılır.
Her ilanda modelin hesapladığı adil oda payı da gösterilir — istenen kiranın
piyasaya uyup uymadığını görürsün.</p>
<p><a class="cta" href="/onboarding">Ücretsiz kayıt ol</a></p>

<h2>Bütçe haritası</h2>
<p>Hangi semtin bütçene uyduğunu tek bakışta görmek için
<a href="/explore">bütçe haritasına</a> bakabilirsin: 968 mahalle, girdiğin bütçeye
göre yeşilden kırmızıya renklenir.</p>

<nav class="links"><strong>Diğer semtler:</strong><br>${komsular}<br>
<a href="/semt/">Tüm semtler</a></nav>
`;

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "WebPage",
    name: title,
    description,
    url,
    inLanguage: "tr-TR",
    isPartOf: { "@type": "WebSite", name: "evdes.tr", url: SITE },
    about: {
      "@type": "Place",
      name: `${d.name}, İstanbul`,
      address: {
        "@type": "PostalAddress",
        addressLocality: d.name,
        addressRegion: "İstanbul",
        addressCountry: "TR",
      },
    },
  };

  return layout({ title, description, canonical: url, jsonLd, body });
}

function indexPage(list) {
  const url = `${SITE}/semt/`;
  const title = "İstanbul semtlerinde oda kiraları ve ev arkadaşı — evdes.tr";
  const description =
    `İstanbul'un ${list.length} ilçesinde kiralık daire ve oda payı medyanları, ` +
    `mahalle kırılımıyla. Üniversite öğrencilerine özel ev arkadaşı platformu.`;

  const satirlar = list
    .map(
      d => `<tr>
<td><a href="/semt/${d.slug}">${esc(d.name)}</a></td>
<td class="num">${money(d.median)}</td>
<td class="num">${money(roomShare(d.median))}</td>
<td class="num">${nf.format(d.list.length)}</td>
</tr>`,
    )
    .join("\n");

  const body = `
<h1>İstanbul'da semt semt oda kiraları</h1>
<p class="lead">${list.length} ilçe · ${nf.format(TOTAL_LISTINGS)} ilan · veriler ${esc(FACTOR.indexedTo)} düzeyinde</p>
<p>Aşağıdaki rakamlar kiralık daire ilanlarının medyanı ve iki yatak odalı bir evde
kişi başına düşen pay. Bir ilçeye tıklayınca mahalle kırılımını görürsün.</p>
<table>
<thead><tr><th>İlçe</th><th class="num">Daire kirası</th><th class="num">Oda payı</th><th class="num">Mahalle</th></tr></thead>
<tbody>
${satirlar}
</tbody>
</table>
<p><a class="cta" href="/onboarding">Ev arkadaşı aramaya başla</a></p>
`;

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: title,
    description,
    url,
    inLanguage: "tr-TR",
  };

  return layout({ title, description, canonical: url, jsonLd, body });
}

// ---- yazma ----------------------------------------------------------------

rmSync(OUT_DIR, { recursive: true, force: true });
mkdirSync(OUT_DIR, { recursive: true });

for (const d of districts) {
  writeFileSync(join(OUT_DIR, `${d.slug}.html`), districtPage(d, districts));
}
writeFileSync(join(OUT_DIR, "index.html"), indexPage(districts));

// Sitemap: statik semt sayfaları + herkese açık uygulama rotaları.
// Giriş gerektiren rotalar (swipe, matches, profile...) DIŞARIDA: içeriği
// yalnızca oturum açanlar görür, dizine eklenmesinin bir anlamı yok.
const bugun = new Date().toISOString().slice(0, 10);
const urls = [
  { loc: `${SITE}/`, pri: "1.0" },
  { loc: `${SITE}/semt/`, pri: "0.9" },
  { loc: `${SITE}/safety`, pri: "0.5" },
  { loc: `${SITE}/onboarding`, pri: "0.6" },
  ...districts.map(d => ({ loc: `${SITE}/semt/${d.slug}`, pri: "0.8" })),
];
writeFileSync(
  join(PUBLIC, "sitemap.xml"),
  `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls
  .map(
    u =>
      `  <url><loc>${u.loc}</loc><lastmod>${bugun}</lastmod><priority>${u.pri}</priority></url>`,
  )
  .join("\n")}
</urlset>
`,
);

console.log(
  `✅ SEO: ${districts.length} semt sayfası + dizin + sitemap ` +
    `(çarpan ×${FACTOR.factor}, ${FACTOR.dataPeriod} → ${FACTOR.indexedTo})`,
);
