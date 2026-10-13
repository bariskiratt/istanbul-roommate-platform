/**
 * Arama motoruna açık her rotaya kendi <head>'ini veren derleme eklentisi.
 *
 * NEDEN: Uygulama tek sayfa; her rota aynı index.html'i alıyordu ve onun
 * canonical'ı "https://evdes.tr/" idi. Yani /explore, /safety, /privacy ve
 * /onboarding Google'a "ben ana sayfanın kopyasıyım" diyordu ve ayrı sayfa
 * olarak dizine girmiyordu. JavaScript çalıştırmayan bağlantı önizlemeleri
 * (WhatsApp, X) de her adreste ana sayfanın başlığını gösteriyordu.
 *
 * NE YAPAR: Derleme bitince dist/index.html'in her açık rota için bir kopyası
 * dist/<rota>/index.html olarak yazılır; başlık, açıklama, canonical ve og
 * etiketleri o rotanınkiyle değişir. Gövde aynı, açılan uygulama aynı.
 * vercel.json bu rotaları kendi kopyasına yönlendirir.
 *
 * Metinler PageMeta'nın okuduğu Türkçe sözlükten gelir: sekmedeki başlık ile
 * arama sonucundaki başlık hep aynı kalır.
 */

/// <reference types="node" />
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";

import type { Plugin } from "vite";

import { translations } from "../src/i18n/translations";
import { fullTitle, INDEXABLE_ROUTES, matchRoute } from "../src/lib/routeMeta";

const SITE = "https://evdes.tr";

const esc = (s: string) =>
  s.replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);

/** index.html'in rotaya göre değişen etiketlerini değiştirir. Her etiket
 *  tam bir kez bulunmalı: index.html'de biri değişir de eşleşme kaçarsa
 *  sessizce ana sayfanın etiketiyle yayına çıkmaktansa derleme patlasın. */
export function withRouteHead(html: string, route: string): string {
  const meta = matchRoute(route);
  const tr = translations.tr;
  const title = esc(fullTitle(meta, tr[meta.title]));
  const desc = esc(tr[meta.desc ?? "meta.homeDesc"]);
  const url = route === "/" ? `${SITE}/` : `${SITE}${route}`;

  const swaps: [RegExp, string][] = [
    [/<title>[^<]*<\/title>/g, `<title>${title}</title>`],
    [/<meta name="description" content="[^"]*"/g, `<meta name="description" content="${desc}"`],
    [/<link rel="canonical" href="[^"]*"/g, `<link rel="canonical" href="${url}"`],
    [/<meta property="og:url" content="[^"]*"/g, `<meta property="og:url" content="${url}"`],
    [/<meta property="og:title" content="[^"]*"/g, `<meta property="og:title" content="${title}"`],
    [
      /<meta property="og:description" content="[^"]*"/g,
      `<meta property="og:description" content="${desc}"`,
    ],
  ];

  let out = html;
  for (const [re, tag] of swaps) {
    const found = out.match(re)?.length ?? 0;
    if (found !== 1) {
      throw new Error(`index.html: ${re.source} ${found} kez bulundu, 1 bekleniyordu`);
    }
    out = out.replace(re, tag);
  }
  return out;
}

export default function routeHeads(): Plugin {
  return {
    name: "evdes-route-heads",
    apply: "build",
    writeBundle(options, bundle) {
      const index = bundle["index.html"];
      if (!options.dir || index?.type !== "asset") {
        throw new Error("route-heads: derlemede index.html bulunamadı");
      }
      const html =
        typeof index.source === "string" ? index.source : new TextDecoder().decode(index.source);

      for (const route of INDEXABLE_ROUTES) {
        const file = join(options.dir, route === "/" ? "" : route.slice(1), "index.html");
        mkdirSync(dirname(file), { recursive: true });
        writeFileSync(file, withRouteHead(html, route));
      }
    },
  };
}
