import { describe, expect, it } from "vitest";
import { describeApiError } from "@/lib/apiError";

const FALLBACK = "İstek başarısız (500)";

describe("describeApiError — düz metin detail", () => {
  it("sunucu metnini olduğu gibi gösterir", () => {
    expect(describeApiError({ detail: "Bu ilanı zaten raporladın." }, FALLBACK)).toEqual({
      message: "Bu ilanı zaten raporladın.",
      field: null,
      reasons: [],
    });
  });

  it("detail alanı açılmadan doğrudan da verilebilir", () => {
    expect(describeApiError("Mesaj gönderilemedi.", FALLBACK).message).toBe(
      "Mesaj gönderilemedi.",
    );
  });

  it("boş metni yedek metinle değiştirir", () => {
    expect(describeApiError({ detail: "   " }, FALLBACK).message).toBe(FALLBACK);
  });
});

describe("describeApiError — sözlük detail (denetim reddi)", () => {
  const body = {
    detail: {
      message:
        "Açıklamada küfür veya ağır hakaret tespit edildi. Bu alanı düzenleyip tekrar deneyin.",
      field: "description",
      reasons: ["kufur:siktir"],
    },
  };

  it("mesaj, alan ve gerekçeleri taşır", () => {
    expect(describeApiError(body, FALLBACK)).toEqual({
      message:
        "Açıklamada küfür veya ağır hakaret tespit edildi. Bu alanı düzenleyip tekrar deneyin.",
      field: "description",
      reasons: ["kufur:siktir"],
    });
  });

  it("başlık reddini de aynı biçimde okur", () => {
    const info = describeApiError(
      { detail: { message: "Başlıkta küfür var.", field: "title", reasons: [] } },
      FALLBACK,
    );
    expect(info.field).toBe("title");
    expect(info.reasons).toEqual([]);
  });

  it("mesajı olmayan sözlükte yedek metne düşer, [object Object] yazmaz", () => {
    const info = describeApiError({ detail: { field: "title" } }, FALLBACK);
    expect(info.message).toBe(FALLBACK);
    expect(info.field).toBe("title");
  });

  it("gerekçeler dizi değilse boş dizi olur", () => {
    expect(describeApiError({ detail: { message: "x", reasons: "kufur" } }, FALLBACK).reasons)
      .toEqual([]);
  });
});

describe("describeApiError — liste detail (Pydantic doğrulama)", () => {
  // 3'ten az fotoğrafla ilan gönderilince gelen gerçek gövde.
  const body = {
    detail: [
      {
        type: "too_short",
        loc: ["body", "photos"],
        msg: "List should have at least 3 items after validation, not 2",
        input: ["a.jpg", "b.jpg"],
      },
    ],
  };

  it("msg alanını gösterir ve alanı loc'tan çıkarır", () => {
    expect(describeApiError(body, FALLBACK)).toEqual({
      message: "List should have at least 3 items after validation, not 2",
      field: "photos",
      reasons: [],
    });
  });

  it("birden çok hatayı birleştirir, tekrarı yazmaz", () => {
    const info = describeApiError(
      {
        detail: [
          { loc: ["body", "title"], msg: "Field required" },
          { loc: ["body", "district"], msg: "Field required" },
          { loc: ["body", "rent"], msg: "Input should be greater than 0" },
        ],
      },
      FALLBACK,
    );
    expect(info.message).toBe("Field required Input should be greater than 0");
    // İlk hatanın alanı taşınır — arayüz kullanıcıyı oraya götürebilsin diye.
    expect(info.field).toBe("title");
  });

  it("dizi indeksini alan adı sanmaz", () => {
    expect(
      describeApiError({ detail: [{ loc: ["body", "photos", 0], msg: "x" }] }, FALLBACK).field,
    ).toBe("photos");
  });

  it("boş listede yedek metne düşer", () => {
    expect(describeApiError({ detail: [] }, FALLBACK).message).toBe(FALLBACK);
  });
});

describe("describeApiError — gövde yoksa", () => {
  it("null gövdede yedek metni verir", () => {
    expect(describeApiError(null, FALLBACK)).toEqual({
      message: FALLBACK,
      field: null,
      reasons: [],
    });
  });

  it("detail alanı olmayan gövdede de çökmez", () => {
    expect(describeApiError({ error: "boom" }, FALLBACK).message).toBe(FALLBACK);
  });
});
