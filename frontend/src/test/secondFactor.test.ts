import { describe, expect, it } from "vitest";
import { needsSecondFactor, type ApiUser } from "@/lib/api";

// Şifreyle girişin iki yanıt biçimi: normal hesapta oturum, yönetici
// hesabında "e-postana gelen kodu gir" (iki adımlı yönetici girişi).
describe("needsSecondFactor", () => {
  it("yönetici yanıtını ikinci adım olarak tanır", () => {
    expect(
      needsSecondFactor({ otp_required: true, detail: "Yönetici hesabı", dev_code: null }),
    ).toBe(true);
  });

  it("oturum yanıtını ikinci adım saymaz", () => {
    const user = { id: 1, email: "ali@uni.edu.tr", is_admin: false } as ApiUser;
    expect(needsSecondFactor({ token: "abc", user })).toBe(false);
  });
});
