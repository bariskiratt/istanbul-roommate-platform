/**
 * Backend zaman damgalarını güvenle Date'e çevirir.
 * Sunucu naive UTC ISO string döndürür ("2026-07-31T10:00:00"); tarayıcı bunu
 * yerel saat sanır ve saatler 3 saat kayar. Dilim bilgisi yoksa UTC varsayılır.
 */
export function parseUtc(iso: string): Date {
  const hasZone = /Z$|[+-]\d{2}:?\d{2}$/.test(iso);
  return new Date(hasZone ? iso : `${iso}Z`);
}
