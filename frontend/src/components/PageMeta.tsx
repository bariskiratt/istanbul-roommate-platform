/**
 * Rotaya özel sekme başlığı ve meta açıklaması.
 *
 * Tek sayfa uygulaması olduğumuz için her rota aynı index.html'i servis
 * ediyordu; sonuç olarak /swipe de /profile de sekmede "evdes.tr — İstanbul'da
 * ev arkadaşı bul" yazıyordu. Geçmiş, yer imleri ve açık sekmeler ayırt
 * edilemiyordu.
 *
 * Sayfa sayfa değil MERKEZÎ yazıldı: her sayfaya ayrı ayrı eklenseydi yeni bir
 * rota eklendiğinde unutulur ve sessizce eski başlıkla kalırdı. Burada
 * eşleşmeyen rota NotFound başlığını alır, yani unutmak görünür olur.
 * Tablonun kendisi lib/routeMeta.ts'te: arama motoruna açık rotaların
 * derlemede üretilen HTML'i de aynı tablodan okunuyor.
 *
 * Rotaların çoğu robots.txt'de kapalı ve arama sonucuna çıkmaz; başlık oradaki
 * kullanıcı deneyimi için. Açık olanlar (INDEXABLE_ROUTES) ayrıca bir açıklama
 * da alıyor.
 */

import { useEffect } from "react";
import { useLocation } from "react-router-dom";

import { useI18n } from "@/i18n";
import { fullTitle, matchRoute } from "@/lib/routeMeta";

function setDescription(text: string) {
  let tag = document.querySelector<HTMLMetaElement>('meta[name="description"]');
  if (!tag) {
    tag = document.createElement("meta");
    tag.name = "description";
    document.head.appendChild(tag);
  }
  tag.content = text;
}

export default function PageMeta() {
  const { pathname } = useLocation();
  const { t } = useI18n();

  useEffect(() => {
    const meta = matchRoute(pathname);
    document.title = fullTitle(meta, t(meta.title));
    setDescription(t(meta.desc ?? "meta.homeDesc"));
  }, [pathname, t]);

  return null;
}
