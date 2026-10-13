/**
 * Arama motoru botu siteyi Türkçe görür (i18n/index.tsx).
 *
 * Googlebot "en-US" bildiriyor; eskiden bu yüzden Google sitenin İngilizce
 * sürümünü diziniyordu.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { detectLang, isCrawler } from "../i18n";

const GOOGLEBOT =
  "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)";
const CHROME =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36";
const IPHONE =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1";

function browser(ua: string, language: string) {
  vi.spyOn(navigator, "userAgent", "get").mockReturnValue(ua);
  vi.spyOn(navigator, "language", "get").mockReturnValue(language);
}

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("bot dili", () => {
  it("botları tanır, tarayıcıları tanımaz", () => {
    expect(isCrawler(GOOGLEBOT)).toBe(true);
    expect(isCrawler("Mozilla/5.0 (compatible; Google-InspectionTool/1.0;)")).toBe(true);
    expect(isCrawler("Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)")).toBe(true);
    expect(isCrawler("Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)")).toBe(true);
    expect(isCrawler(CHROME)).toBe(false);
    expect(isCrawler(IPHONE)).toBe(false);
  });

  it("İngilizce bildiren Googlebot Türkçe görür", () => {
    browser(GOOGLEBOT, "en-US");
    expect(detectLang()).toBe("tr");
  });

  it("insanlar için davranış aynı", () => {
    browser(CHROME, "en-US");
    expect(detectLang()).toBe("en");
    browser(IPHONE, "tr-TR");
    expect(detectLang()).toBe("tr");
    localStorage.setItem("lang", "en");
    browser(GOOGLEBOT, "en-US");
    expect(detectLang()).toBe("en");
  });
});
