/**
 * ALTERNATİF SEMT PANELİ SESSİZCE BOŞ KALMAMALI.
 *
 * Özellik bir süre kapalı kaldı; sebeplerinden biri, öğrenci bütçesinde
 * (20.000 TL) panelin çoğu hedef için hiçbir şey göstermemesiydi. Sunucu artık
 * dört durumu ayırıyor ve panel her birine ayrı cümle kuruyor:
 *
 *   unreachable  -> hedef raylı sisteme yürüme mesafesinde değil
 *   fits         -> bütçeye uyan (ya da sınırda) yakın mahalleler
 *   over_budget  -> yakında daha ucuzu var ama bütçeye uymuyor: en ucuzlar
 *   none         -> yakında hedeften ucuz mahalle yok
 *
 * Eski panel "8 durak" yazıyordu; o sayı aslında 3 durak + 1 aktarmanın ağ
 * maliyetiydi. Rota satırı artık durak ve aktarmayı ayrı söylüyor.
 *
 * Gövdeler sunucunun gerçek yanıtlarından (kayıtlı veriyle) kopyalandı.
 */

import { describe, expect, it } from "vitest";

import { altListed, altPanelState, routeParts } from "@/lib/alternatives";
import { translations } from "@/i18n/translations";
import type { AlternativesResponse } from "@/lib/api";

const BEBEK_30K: AlternativesResponse = {
  target: { id: 28, name: "Bebek", district: "Beşiktaş", price: 190440, low_confidence: false, lat: 41.07897, lon: 29.04398 },
  reachable: true,
  budget: 30000,
  max_minutes: 45,
  recommendations: [
    { id: 472, name: "Yeşilce", district: "Kağıthane", price: 33120, low_confidence: false, lat: 41.09565, lon: 29.00058, minutes: 34, stops: 4, transfers: 1, walk_minutes: 6, status: "borderline", saving: 157320 },
    { id: 466, name: "Sultan Selim", district: "Kağıthane", price: 33120, low_confidence: false, lat: 41.09098, lon: 28.9979, minutes: 39, stops: 4, transfers: 1, walk_minutes: 11, status: "borderline", saving: 157320 },
  ],
  cheapest: [],
};

const CAFERAGA_20K: AlternativesResponse = {
  target: { id: 650, name: "Caferağa", district: "Kadıköy", price: 74520, low_confidence: false, lat: 40.98509, lon: 29.02481 },
  reachable: true,
  budget: 20000,
  max_minutes: 45,
  recommendations: [],
  cheapest: [
    { id: 342, name: "Yedikule", district: "Fatih", price: 24840, low_confidence: true, lat: 40.99398, lon: 28.92417, minutes: 37, stops: 4, transfers: 1, walk_minutes: 9, status: "expensive", saving: 49680, over_budget: 4840 },
    { id: 317, name: "Aksaray", district: "Fatih", price: 31464, low_confidence: false, lat: 41.00332, lon: 28.94931, minutes: 30, stops: 3, transfers: 1, walk_minutes: 4, status: "expensive", saving: 43056, over_budget: 11464 },
  ],
};

const SINANPASA: AlternativesResponse = {
  target: { id: 44, name: "Sinanpaşa", district: "Beşiktaş", price: 57960, low_confidence: false, lat: 41.04276, lon: 29.00487 },
  reachable: false,
  reason: "not_near_rail",
  budget: 30000,
  max_minutes: 45,
  recommendations: [],
  cheapest: [],
};

// Küçükçekmece / Atatürk, 20.000 TL: zaten yakınındaki en ucuz mahalle.
const NOTHING_CHEAPER: AlternativesResponse = {
  target: { id: 900, name: "Atatürk", district: "Küçükçekmece", price: 17388, low_confidence: false, lat: 41.0, lon: 28.78 },
  reachable: true,
  budget: 20000,
  max_minutes: 45,
  recommendations: [],
  cheapest: [],
};

describe("altPanelState / altListed", () => {
  it("bütçeye uyanlar varsa onları listeler", () => {
    expect(altPanelState(BEBEK_30K)).toBe("fits");
    expect(altListed(BEBEK_30K).map((c) => c.name)).toEqual(["Yeşilce", "Sultan Selim"]);
  });

  it("bütçeye uyan yoksa boş kalmaz, en ucuz yakınları aşım miktarıyla gösterir", () => {
    expect(altPanelState(CAFERAGA_20K)).toBe("over_budget");
    const listed = altListed(CAFERAGA_20K);
    expect(listed.map((c) => c.name)).toEqual(["Yedikule", "Aksaray"]);
    expect(listed[0].over_budget).toBe(4840);
  });

  it("raylı sisteme uzak hedefi ve 'daha ucuzu yok' durumunu ayırır", () => {
    expect(altPanelState(SINANPASA)).toBe("unreachable");
    expect(altListed(SINANPASA)).toEqual([]);
    expect(altPanelState(NOTHING_CHEAPER)).toBe("none");
    expect(altListed(NOTHING_CHEAPER)).toEqual([]);
  });
});

describe("routeParts", () => {
  it("durak ve aktarmayı ayrı söyler", () => {
    const tr = (c: AlternativesResponse["recommendations"][number]) =>
      routeParts(c).map((p) => p.key);
    expect(tr(BEBEK_30K.recommendations[0])).toEqual([
      "map.altStops",
      "map.altTransfers",
      "map.altWalk",
    ]);
    expect(routeParts(BEBEK_30K.recommendations[0])[0].vars).toEqual({ count: 4 });
  });

  it("aynı istasyondaki mahallede durak/aktarma yazmaz", () => {
    const same = { ...BEBEK_30K.recommendations[0], stops: 0, transfers: 0 };
    expect(routeParts(same).map((p) => p.key)).toEqual(["map.altSameStation", "map.altWalk"]);
    const direct = { ...BEBEK_30K.recommendations[0], stops: 2, transfers: 0 };
    expect(routeParts(direct).map((p) => p.key)).toEqual([
      "map.altStops",
      "map.altDirect",
      "map.altWalk",
    ]);
  });
});

describe("panel metinleri", () => {
  it("panelin kullandığı her anahtar iki sözlükte de tanımlı", () => {
    const keys = [
      "map.altButton",
      "map.altCalculating",
      "map.altFailed",
      "map.altTarget",
      "map.altPanelTitle",
      "map.altTargetPrice",
      "map.altTargetLowConfidence",
      "map.altRule",
      "map.altItem",
      "map.altMinutes",
      "map.altStops",
      "map.altSameStation",
      "map.altTransfers",
      "map.altDirect",
      "map.altWalk",
      "map.altBorderline",
      "map.altLowConfidence",
      "map.altNoneInBudget",
      "map.altOverBudget",
      "map.altNone",
      "map.altUnreachable",
      "map.altFootnote",
    ] as const;
    for (const key of keys) {
      expect(translations.tr[key], `tr: ${key}`).toBeTruthy();
      expect(translations.en[key], `en: ${key}`).toBeTruthy();
    }
  });
});
