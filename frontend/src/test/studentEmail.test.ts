/**
 * Kayıt formunun "üniversite adresi" ipucu sunucunun kuralıyla aynı mı.
 *
 * Neden: istemci daha dar bir kural uygularsa sunucunun kabul ettiği
 * öğrenci kapıda kalır ve kimse fark etmez (sunucuya istek hiç gitmez).
 * Bu tam olarak @sabanciuniv.edu adreslerinde yaşandı.
 */

// Vitest 4 Node tiplerini artık kendiliğinden getirmiyor; bu test dosyası
// diskten okuduğu için tipler buradan eklenir.
/// <reference types="node" />
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { NON_EDU_TR_UNIVERSITY_DOMAINS, isStudentEmail } from "../lib/studentEmail";

const UNIVERSITIES = join(__dirname, "../../../backend/app/universities.py");

describe("isStudentEmail", () => {
  it("edu.tr ve alt alanlarını kabul ediyor", () => {
    expect(isStudentEmail("ali@itu.edu.tr")).toBe(true);
    expect(isStudentEmail("ali@ogr.iu.edu.tr")).toBe(true);
    expect(isStudentEmail("ALI@STD.YILDIZ.EDU.TR")).toBe(true);
  });

  it("sabanciuniv.edu gibi .edu.tr olmayan üniversite adreslerini kabul ediyor", () => {
    expect(isStudentEmail("ayse@sabanciuniv.edu")).toBe(true);
    expect(isStudentEmail("ayse@alumni.sabanciuniv.edu")).toBe(true);
  });

  it("başka adresleri reddediyor", () => {
    expect(isStudentEmail("ali@gmail.com")).toBe(false);
    expect(isStudentEmail("ali@edu.tr.example.com")).toBe(false);
    expect(isStudentEmail("ali@notsabanciuniv.edu")).toBe(false);
    expect(isStudentEmail("ali.edu.tr")).toBe(false);
    expect(isStudentEmail("")).toBe(false);
  });

  it("bilinen .edu.tr dışı alan adları sunucudaki listeyle aynı", () => {
    const src = readFileSync(UNIVERSITIES, "utf8");
    const body = src.slice(src.indexOf("DOMAINS"), src.indexOf("\n}\n"));
    const domains = [...body.matchAll(/^\s+"([^"]+)":/gm)].map(m => m[1]);
    expect(domains.length).toBeGreaterThan(10);
    const nonEduTr = domains.filter(d => d !== "edu.tr" && !d.endsWith(".edu.tr"));
    expect([...NON_EDU_TR_UNIVERSITY_DOMAINS].sort()).toEqual(nonEduTr.sort());
  });
});
