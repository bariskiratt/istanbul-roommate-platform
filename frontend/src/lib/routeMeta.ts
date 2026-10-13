/**
 * Rota -> sekme başlığı/meta açıklaması tablosu.
 *
 * İki yerde okunur: tarayıcıda components/PageMeta.tsx (rota değişince
 * sekme başlığı), derlemede scripts/route-heads.ts (arama motoruna açık her
 * rotanın kendi HTML'i). Bu yüzden React'e ve "@/" kısayoluna bağımlı değil:
 * vite.config.ts bu dosyayı Node'da içe aktarıyor.
 */

import { BRAND } from "./brand";
import type { TranslationKey } from "../i18n/translations";

export type Meta = { title: TranslationKey; desc?: TranslationKey };

/** Yol -> başlık/açıklama anahtarı. Dinamik parçalar ":" ile yazılır. */
export const ROUTES: Record<string, Meta> = {
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

/**
 * Arama motoruna açık uygulama rotaları. Her biri derlemede kendi
 * dist/<rota>/index.html dosyasını alır (doğru canonical, başlık ve
 * açıklamayla) ve vercel.json o dosyaya yönlendirir. Buraya eklenen rota
 * robots.txt'de açık olmalı; giriş sayfası dışındakiler sitemap'te de yer
 * alır (bkz. src/test/routeHeads.test.ts).
 */
export const INDEXABLE_ROUTES = [
  "/",
  "/onboarding",
  "/login",
  "/explore",
  "/safety",
  "/privacy",
] as const;

export const NOT_FOUND: Meta = { title: "meta.notFound" };

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

/** Sekmede ve arama sonucunda görünen tam başlık. Ana sayfanın başlığı
 *  markayı zaten içeriyor; tekrar eklenmez. */
export function fullTitle(meta: Meta, label: string): string {
  return meta.title === "meta.home" ? label : `${label} — ${BRAND}`;
}
