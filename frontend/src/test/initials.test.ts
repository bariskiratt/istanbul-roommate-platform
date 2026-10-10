import { describe, expect, it } from "vitest";
import { initials } from "@/lib/utils";

// Fotoğrafı olmayan kullanıcının avatarı (src/components/UserAvatar.tsx).
describe("initials", () => {
  it("ilk ve son kelimenin baş harfini alır", () => {
    expect(initials("Ayşe Yılmaz")).toBe("AY");
    expect(initials("Mehmet Ali Kaya")).toBe("MK");
    expect(initials("deniz")).toBe("D");
  });

  it("büyük harfi Türkçe kuralıyla yapar", () => {
    expect(initials("ilker ışık")).toBe("İI");
  });

  it("boşlukları ve boş adı tolere eder", () => {
    expect(initials("  Ece   Demir  ")).toBe("ED");
    expect(initials("")).toBe("");
    expect(initials("   ")).toBe("");
  });

  it("iki birimlik karakteri bölmez", () => {
    expect(initials("😀 Can")).toBe("😀C");
  });
});
