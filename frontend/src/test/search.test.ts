import { describe, expect, it } from "vitest";
import { filterByQuery, matchesQuery, normalizeText } from "@/lib/search";

// Konum seçicinin aradığı gerçek veriden örnekler (38 ilçe / 539 mahalle).
const DISTRICTS = [
  "Beşiktaş", "Üsküdar", "Şişli", "Bağcılar", "Kadıköy", "Beyoğlu", "Çekmeköy",
];

describe("normalizeText", () => {
  it("Türkçe harfleri ASCII karşılığına indirir", () => {
    expect(normalizeText("Beşiktaş")).toBe("besiktas");
    expect(normalizeText("Üsküdar")).toBe("uskudar");
    expect(normalizeText("Şişli")).toBe("sisli");
    expect(normalizeText("Bağcılar")).toBe("bagcilar");
    expect(normalizeText("Caferağa Mah.")).toBe("caferaga mah.");
  });

  it("noktalı/noktasız I ayrımını locale'den bağımsız çözer", () => {
    // Türkçe locale'de "I".toLocaleLowerCase() "ı" verirdi; burada ikisi de "i".
    expect(normalizeText("İSTANBUL")).toBe("istanbul");
    expect(normalizeText("ISTANBUL")).toBe("istanbul");
    expect(normalizeText("Ihlamurkuyu Mah.")).toBe("ihlamurkuyu mah.");
  });

  it("boş metni bozmaz", () => {
    expect(normalizeText("")).toBe("");
  });
});

describe("matchesQuery", () => {
  // Görevde istenen beş örnek: Türkçe karakter yazmadan hepsi bulunmalı.
  it.each([
    ["besiktas", "Beşiktaş"],
    ["uskudar", "Üsküdar"],
    ["sisli", "Şişli"],
    ["bagcilar", "Bağcılar"],
    ["cafer", "Caferağa Mah."],
  ])("%s -> %s", (query, text) => {
    expect(matchesQuery(text, query)).toBe(true);
  });

  it("Türkçe yazılan sorgu da eşleşir", () => {
    expect(matchesQuery("Beşiktaş", "beşiktaş")).toBe(true);
    expect(matchesQuery("Üsküdar", "ÜSKÜDAR")).toBe(true);
  });

  it("boş sorgu her şeyle eşleşir", () => {
    expect(matchesQuery("Kadıköy", "")).toBe(true);
    expect(matchesQuery("Kadıköy", "   ")).toBe(true);
  });

  it("ilgisiz sorgu eşleşmez", () => {
    expect(matchesQuery("Beşiktaş", "kadikoy")).toBe(false);
  });

  it("çok kelimeli sorguda tüm parçalar aranır", () => {
    expect(matchesQuery("Caferağa Mah.", "cafer mah")).toBe(true);
    expect(matchesQuery("Caferağa Mah.", "cafer sokak")).toBe(false);
  });
});

describe("filterByQuery", () => {
  it("listeyi Türkçe duyarsız süzer", () => {
    expect(filterByQuery(DISTRICTS, "cekmekoy", d => d)).toEqual(["Çekmeköy"]);
    expect(filterByQuery(DISTRICTS, "si", d => d)).toEqual(["Beşiktaş", "Şişli"]);
  });

  it("boş sorguda liste aynen döner", () => {
    expect(filterByQuery(DISTRICTS, "", d => d)).toEqual(DISTRICTS);
  });
});
