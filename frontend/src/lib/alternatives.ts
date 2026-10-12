/**
 * Alternatif semt panelinin kararları (bileşenden ayrı, test edilebilsin).
 *
 * Sunucu (`GET /api/alternatives`) dört durumdan birini anlatır; panel hangi
 * cümleyi ve hangi listeyi göstereceğini buradan öğrenir. Rota satırı da
 * ("4 durak · 1 aktarma · istasyona 6 dk yürüme") anahtar + değişken olarak
 * kurulur ki dil değişince ekrandaki metin de değişsin.
 */
import type { AltCandidate, AlternativesResponse } from "@/lib/api";
import type { TranslationKey } from "@/i18n/translations";

export type AltPanelState =
  /** Hedef raylı sisteme yürüme mesafesinde değil. */
  | "unreachable"
  /** Bütçeye uyan (ya da sınırda) yakın mahalleler var. */
  | "fits"
  /** Yakında daha ucuzu var ama hiçbiri bütçeye uymuyor: en ucuzları göster. */
  | "over_budget"
  /** Yakında hedeften ucuz hiçbir mahalle yok. */
  | "none";

export function altPanelState(alt: AlternativesResponse): AltPanelState {
  if (!alt.reachable) return "unreachable";
  if (alt.recommendations.length > 0) return "fits";
  if (alt.cheapest.length > 0) return "over_budget";
  return "none";
}

/** Panelde listelenen mahalleler; numaraları haritadaki iğnelerle aynı. */
export function altListed(alt: AlternativesResponse): AltCandidate[] {
  const state = altPanelState(alt);
  if (state === "fits") return alt.recommendations;
  if (state === "over_budget") return alt.cheapest;
  return [];
}

export type RoutePart = { key: TranslationKey; vars?: Record<string, number> };

/** "4 durak · 1 aktarma · istasyona 6 dk yürüme" satırının parçaları. */
export function routeParts(c: AltCandidate): RoutePart[] {
  const parts: RoutePart[] = [
    c.stops === 0
      ? { key: "map.altSameStation" }
      : { key: "map.altStops", vars: { count: c.stops } },
  ];
  if (c.stops > 0) {
    parts.push(
      c.transfers === 0
        ? { key: "map.altDirect" }
        : { key: "map.altTransfers", vars: { count: c.transfers } },
    );
  }
  parts.push({ key: "map.altWalk", vars: { count: c.walk_minutes } });
  return parts;
}
