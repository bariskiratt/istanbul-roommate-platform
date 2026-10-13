/**
 * main'in üretim yayınını Vercel değil GitHub Actions yapar.
 *
 * Neden: Vercel main'e gelen commit'i CI'ı ve Render'ı beklemeden yayına
 * alıyordu; birkaç dakika boyunca yeni frontend eski backend'le konuşuyordu.
 * vercel.json'daki bu ayar Vercel'in main'i kendiliğinden yayınlamasını kapatır,
 * .github/workflows/frontend-deploy.yml de frontend'i ancak CI yeşil ve backend
 * Render'da yayındayken üretime alır. Ayar silinirse ikisi aynı commit'i ayrı
 * ayrı yayınlar ve beklemenin hiçbir anlamı kalmaz; testten başka hiçbir şey
 * bunu fark ettirmez.
 */

import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const root = join(__dirname, "../..");

describe("üretim yayını", () => {
  it("Vercel main'i kendiliğinden yayınlamıyor", () => {
    const cfg = JSON.parse(readFileSync(join(root, "vercel.json"), "utf8"));
    expect(cfg.git?.deploymentEnabled?.main).toBe(false);
  });

  it("main'i yayınlayan iş akışı yerinde", () => {
    expect(existsSync(join(root, "../.github/workflows/frontend-deploy.yml"))).toBe(true);
  });
});
