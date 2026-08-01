/**
 * Sunucu hata gövdesini kullanıcıya gösterilebilir tek bir biçime indirger.
 *
 * FastAPI'nin `detail` alanı ÜÇ ayrı biçimde gelebiliyor ve üçü de arayüzde
 * düzgün görünmeli:
 *
 *   1) düz metin — çoğu uç:
 *        {"detail": "Bu ilanı zaten raporladın."}
 *   2) sözlük — ilan denetimi reddi (alan bazlı):
 *        {"detail": {"message": "Açıklamada küfür …", "field": "description",
 *                    "reasons": ["kufur:siktir"]}}
 *   3) liste — Pydantic doğrulama hatası (ör. 3'ten az fotoğraf):
 *        {"detail": [{"type": "too_short", "loc": ["body", "photos"],
 *                     "msg": "List should have at least 3 items …"}]}
 *
 * Eskiden yalnızca (1) okunuyordu; (2) ve (3) geldiğinde kullanıcı
 * "[object Object]" görüyordu. Bu yardımcı saftır (i18n/ağ bağımlılığı yok):
 * gösterilecek yedek metni çağıran hazır verir.
 */

/** Ayrıştırılmış hata: her zaman gösterilebilir bir `message` içerir. */
export interface ErrorDetailInfo {
  /** Kullanıcıya gösterilecek metin; hiçbir zaman boş değildir. */
  message: string;
  /**
   * Hatanın ait olduğu form alanı. Denetim reddinde "title" ya da
   * "description"; doğrulama hatasında alan adı (ör. "photos"). Bilinmiyorsa
   * null.
   */
  field: string | null;
  /** Denetimin gerekçe kodları ("kufur:siktir" gibi); yoksa boş dizi. */
  reasons: string[];
}

/** Metin ise kırpılmış hâlini, değilse null döndürür (boş metin de null). */
const asText = (value: unknown): string | null => {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
};

/**
 * Pydantic `loc` dizisinden alan adını çıkarır: ["body", "photos"] → "photos".
 * Gövde/sorgu ön ekleri ve dizi indeksleri atlanır, en sondaki alan adı alınır
 * (["body", "photos", 0] → "photos").
 */
const fieldFromLoc = (loc: unknown): string | null => {
  if (!Array.isArray(loc)) return null;
  const parts = loc.filter(
    (part): part is string =>
      typeof part === "string" && !["body", "query", "path", "header"].includes(part),
  );
  return parts.length ? parts[parts.length - 1] : null;
};

/** Liste biçimi (Pydantic doğrulama hatası). */
const fromList = (items: unknown[], fallback: string): ErrorDetailInfo => {
  const messages: string[] = [];
  let field: string | null = null;
  for (const item of items) {
    const plain = asText(item);
    if (plain) {
      if (!messages.includes(plain)) messages.push(plain);
      continue;
    }
    if (!item || typeof item !== "object") continue;
    const record = item as Record<string, unknown>;
    const msg = asText(record.msg) ?? asText(record.message);
    if (msg && !messages.includes(msg)) messages.push(msg);
    if (field === null) field = fieldFromLoc(record.loc);
  }
  return {
    message: messages.length ? messages.join(" ") : fallback,
    field,
    reasons: [],
  };
};

/** Sözlük biçimi (denetim reddi). */
const fromRecord = (record: Record<string, unknown>, fallback: string): ErrorDetailInfo => ({
  message: asText(record.message) ?? fallback,
  field: asText(record.field),
  reasons: Array.isArray(record.reasons)
    ? record.reasons.map(asText).filter((r): r is string => r !== null)
    : [],
});

/**
 * Hata gövdesini ayrıştırır. `body` ya doğrudan `detail` değeri ya da tüm
 * yanıt gövdesi olabilir; ikinci durumda `detail` alanı kendiliğinden açılır.
 * `fallback` okunabilir bir metin çıkmadığında kullanılır (çağıran bunu
 * kendi dilinde verir).
 */
export function describeApiError(body: unknown, fallback: string): ErrorDetailInfo {
  const detail =
    body && typeof body === "object" && !Array.isArray(body) && "detail" in body
      ? (body as { detail: unknown }).detail
      : body;

  const plain = asText(detail);
  if (plain) return { message: plain, field: null, reasons: [] };
  if (Array.isArray(detail)) return fromList(detail, fallback);
  if (detail && typeof detail === "object")
    return fromRecord(detail as Record<string, unknown>, fallback);
  return { message: fallback, field: null, reasons: [] };
}
