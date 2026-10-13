/**
 * Semt adına bulunma eki: "Kadıköy'de", "Beşiktaş'ta", "Adalar'da".
 *
 * Semt sayfaları eki elle "'de" diye yazıyordu; 38 semtin 17'sinde başlık
 * yanlış Türkçeydi ("Adalar'de", "Beşiktaş'de", "Beyoğlu'de"). Arama
 * sonucundan gelen biri sayfayı ilk bu başlıkla görüyor.
 *
 * Ayrı dosyada, çünkü generate-seo.mjs import edilir edilmez tüm siteyi
 * üretiyor; testin yalnızca bu fonksiyona erişebilmesi gerekiyor.
 */

const KALIN = "aıou";
const UNLU = "aeıioöuü";
// Sert ünsüzle biten addan sonra "d" -> "t" (Fatih'te, Pendik'te).
const SERT = "çfhkpsşt";

// Tamlama ekiyle biten adlar araya "n" alır: Beyoğlu'nda, Zeytinburnu'nda.
// Kural yazımdan çıkarılamaz (Şişli de "i" ile bitiyor ama Şişli'de), o
// yüzden listedir. Veriye bu biçimde yeni bir ilçe gelirse buraya eklenir.
const TAMLAMA = new Set(["Beyoğlu", "Zeytinburnu", "Beylikdüzü"]);

export function locative(name) {
  const ad = name.trim();
  const kucuk = ad.toLocaleLowerCase("tr");
  const sesliler = [...kucuk].filter(h => UNLU.includes(h));
  const son = sesliler[sesliler.length - 1] ?? "e";
  const a = KALIN.includes(son) ? "a" : "e";
  if (TAMLAMA.has(ad)) return `${ad}'nd${a}`;
  const d = SERT.includes(kucuk[kucuk.length - 1]) ? "t" : "d";
  return `${ad}'${d}${a}`;
}
