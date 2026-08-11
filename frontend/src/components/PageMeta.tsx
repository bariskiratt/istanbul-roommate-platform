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
 *
 * Rotaların çoğu robots.txt'de kapalı ve arama sonucuna çıkmaz; başlık oradaki
 * kullanıcı deneyimi için. Açık olanlar ("/", "/onboarding", "/explore",
 * "/safety", "/login") ayrıca bir açıklama da alıyor.
 */

import { useEffect } from "react";
import { useLocation } from "react-router-dom";

import { useI18n } from "@/i18n";
import type { TranslationKey } from "@/i18n/translations";
import { BRAND } from "@/lib/brand";

type Meta = { title: TranslationKey; desc?: TranslationKey };

/** Yol -> başlık/açıklama anahtarı. Dinamik parçalar ":" ile yazılır. */
const ROUTES: Record<string, Meta> = {
  "/": { title: "meta.home", desc: "meta.homeDesc" },
  "/onboarding": { title: "meta.onboarding", desc: "meta.onboardingDesc" },
  "/login": { title: "meta.login", desc: "meta.loginDesc" },
  "/explore": { title: "meta.explore", desc: "meta.exploreDesc" },
  "/safety": { title: "meta.safety", desc: "meta.safetyDesc" },
  "/privacy": { title: "meta.privacy", desc: "meta.privacyDesc" },
  "/swipe": { title: "meta.swipe" },
  "/notifications": { title: "meta.notifications" },
  "/matches": { title: "meta.matches" },
  "/messages": { title: "meta.messages" },
  "/chat/:matchId": { title: "meta.chat" },
  "/profile": { title: "meta.profile" },
  "/profile/edit": { title: "meta.profileEdit" },
  "/create-listing": { title: "meta.createListing" },
  "/listings": { title: "meta.listings" },
  "/settings": { title: "meta.settings" },
  "/settings/account": { title: "meta.accountSettings" },
  "/admin": { title: "meta.admin" },
};

const NOT_FOUND: Meta = { title: "meta.notFound" };

/** "/chat/42" -> "/chat/:matchId". Segment sayısı tutan kalıpta ":" ile
 *  başlayan parçalar her değeri kabul eder. */
export function matchRoute(pathname: string): Meta {
  if (ROUTES[pathname]) return ROUTES[pathname];

  const parts = pathname.split("/").filter(Boolean);
  for (const [pattern, meta] of Object.entries(ROUTES)) {
    const want = pattern.split("/").filter(Boolean);
    if (want.length !== parts.length) continue;
    if (want.every((w, i) => w.startsWith(":") || w === parts[i])) return meta;
  }
  return NOT_FOUND;
}

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
    const label = t(meta.title);
    // Ana sayfanın başlığı zaten markayı içeriyor; tekrar eklemeyelim.
    document.title = meta.title === "meta.home" ? label : `${label} — ${BRAND}`;
    setDescription(t(meta.desc ?? "meta.homeDesc"));
  }, [pathname, t]);

  return null;
}
