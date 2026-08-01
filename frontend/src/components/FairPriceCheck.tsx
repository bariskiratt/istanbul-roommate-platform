import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Sparkles, TrendingUp, TrendingDown, Check } from "lucide-react";
import { estimatePrice, type EstimateResponse } from "@/lib/api";
import { useI18n } from "@/i18n";
import type { TranslationKey } from "@/i18n/translations";

// Hata ya bir çeviri anahtarı ya da backend'den gelen ham metindir. Çevrilmiş
// dize state'te tutulsaydı dil değiştirildiğinde eski dilde donup kalırdı.
type FieldError = { key: TranslationKey } | { text: string } | null;

interface Props {
  district: string;
  /**
   * Formda seçilmiş mahalle. Panelin TEK mahalle kaynağıdır.
   *
   * Eskiden panelin kendi mahalle listesi vardı ve seçim boşken ilçenin İLK
   * mahallesine düşüyordu: kullanıcı "Kadıköy" bandına baktığını sanırken
   * panel sessizce bir mahalleyi hesaplıyor, yayınlanan ilan ise mahallesiz
   * olduğu için ilçe geneline düşüp BAŞKA bir bant gösteriyordu. Artık panel
   * ile ilanın fiyatı aynı girdiden çıkıyor.
   */
  neighborhood?: string;
  /** İlan verenin istediği kira; adil bantla karşılaştırmak için. */
  askingPrice?: number;
  /** "2+1" gibi oda bilgisi; oda sayısını buradan türetiriz. */
  roomCount?: string;
}

// "2+1" -> {room: 2, living: 1}
function parseRooms(roomCount?: string): { room: number; living: number } {
  const m = roomCount?.match(/^(\d+)\+(\d+)$/);
  if (m) return { room: Math.max(1, Number(m[1])), living: Number(m[2]) };
  return { room: 2, living: 1 };
}

const verdictStyles = {
  fair: { cls: "bg-green-500/10 border-green-500/40 text-foreground", icon: Check, key: "fair.verdictFair" },
  above: { cls: "bg-red-500/10 border-red-500/40 text-foreground", icon: TrendingUp, key: "fair.verdictAbove" },
  below: { cls: "bg-yellow-500/10 border-yellow-500/40 text-foreground", icon: TrendingDown, key: "fair.verdictBelow" },
} as const;

// "2026-01" -> "Oca 2026" / "Jan 2026"
const fmtPeriod = (p: string, locale: string) => {
  const [y, m] = p.split("-").map(Number);
  if (!y || !m) return p;
  return new Date(y, m - 1, 1).toLocaleDateString(locale, { month: "short", year: "numeric" });
};

/**
 * Adil fiyat danışmanı: ilçe + birkaç ek özellikten, backend'deki ML modelini
 * (/api/estimate) kullanarak adil kira aralığını gösterir ve ilan verenin
 * istediği kirayı bu bantla karşılaştırır.
 */
const FairPriceCheck = ({
  district,
  neighborhood = "",
  askingPrice,
  roomCount,
}: Props) => {
  const { t, n: fmt, locale } = useI18n();
  const [area, setArea] = useState("90");
  const [age, setAge] = useState("15");
  const [floor, setFloor] = useState("3");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<FieldError>(null);
  const [result, setResult] = useState<EstimateResponse | null>(null);

  // Konum değişince eldeki sonuç artık o konuma ait değil.
  useEffect(() => {
    setResult(null);
    setError(null);
  }, [district, neighborhood]);

  const analyze = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const { room, living } = parseRooms(roomCount);
      const res = await estimatePrice({
        district,
        neighborhood,
        room,
        living_room: living,
        area: Number(area),
        age: Number(age),
        floor: Number(floor),
        asking_price: askingPrice && askingPrice > 0 ? askingPrice : undefined,
        // Ev arkadaşı ilanı: istenen kira tek odanın payı, kıyas oda bazında
        basis: "room",
      });
      setResult(res);
    } catch (e) {
      setError({ text: (e as Error).message });
    } finally {
      setLoading(false);
    }
  };

  if (!district) return null;

  return (
    <div className="card-listing p-5 space-y-4 border-2 border-primary/20">
      <div className="flex items-center gap-2">
        <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center">
          <Sparkles className="w-5 h-5 text-primary" />
        </div>
        <div>
          <h3 className="font-bold text-foreground">{t("fair.checkTitle")}</h3>
          <p className="text-xs text-muted-foreground">{t("fair.checkSub")}</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        {/* Mahalle yukarıdaki konum seçicisinden gelir; panelin ayrı bir
            listesi yoktur (bkz. Props.neighborhood). Seçilmemişse tahmin
            yapılmaz: sessizce bir mahalle varsaymak, yayınlanacak ilanın
            fiyatından farklı bir bant göstermek olurdu. */}
        <div className="col-span-2 space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground">{t("fair.neighborhood")}</label>
          <div className="h-11 rounded-xl bg-muted/50 border border-border px-3 flex items-center text-sm text-foreground">
            {neighborhood || (
              <span className="text-muted-foreground">{t("fair.pickNeighborhood")}</span>
            )}
          </div>
        </div>
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground">{t("fair.area")}</label>
          <Input type="number" value={area} onChange={(e) => setArea(e.target.value)} className="h-11 rounded-xl" />
        </div>
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground">{t("fair.buildingAge")}</label>
          <Input type="number" value={age} onChange={(e) => setAge(e.target.value)} className="h-11 rounded-xl" />
        </div>
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground">{t("fair.floor")}</label>
          <Input type="number" value={floor} onChange={(e) => setFloor(e.target.value)} className="h-11 rounded-xl" />
        </div>
        <div className="flex items-end">
          <Button
            type="button"
            onClick={analyze}
            disabled={loading || !neighborhood}
            className="w-full h-11 rounded-xl font-semibold"
          >
            {t(loading ? "fair.calculating" : "fair.submit")}
          </Button>
        </div>
      </div>

      {error && (
        <p className="text-xs text-destructive">
          {"key" in error ? t(error.key) : error.text}
        </p>
      )}

      {result && (
        <div className="space-y-3 pt-1">
          {/* Oda payı — ev arkadaşından istenecek adil kira */}
          <div className="text-center">
            <div className="text-2xl font-bold tabular-nums text-primary">
              {fmt(result.room_low)} – {fmt(result.room_high)} {t("common.currency")}
            </div>
            <div className="text-xs text-muted-foreground">
              {t("fair.roomShareLabel", { mid: fmt(result.room_mid) })}
              {result.room_share > 1 &&
                t("fair.roomShareSplit", { rooms: result.room_share })}
            </div>
          </div>

          {/* Dairenin tamamı — referans */}
          <div className="text-center text-xs text-muted-foreground">
            {t("fair.wholeFlat")}{" "}
            <span className="font-semibold text-foreground tabular-nums">
              {fmt(result.fair_low)} – {fmt(result.fair_high)} {t("common.currency")}
            </span>
          </div>

          {result.verdict && (() => {
            const v = verdictStyles[result.verdict];
            const Icon = v.icon;
            const sign = (result.deviation_pct ?? 0) > 0 ? "+" : "";
            return (
              <div className={`rounded-xl border px-3 py-2.5 text-sm flex items-start gap-2 ${v.cls}`}>
                <Icon className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <span>
                  {t(v.key)}{" "}
                  {t("fair.deviation", {
                    asking: fmt(result.asking_price ?? 0),
                    sign,
                    dev: result.deviation_pct ?? 0,
                  })}
                </span>
              </div>
            );
          })()}

          <p className="text-[11px] text-muted-foreground leading-relaxed">
            {/* Endeksleme kapalıyken "bugüne güncellendi" demek yanlış olur;
                tahmin veri döneminin fiyat düzeyinde kalır ve bu söylenir. */}
            {result.indexed
              ? t("fair.disclaimer", {
                  period: fmtPeriod(result.data_period, locale),
                  indexed: fmtPeriod(result.indexed_to, locale),
                  factor: result.index_factor.toFixed(3),
                  err: result.median_error_pct,
                })
              : t("fair.disclaimerNotIndexed", {
                  period: fmtPeriod(result.data_period, locale),
                  err: result.median_error_pct,
                })}
            {!result.known_neighborhood && t("fair.unknownNeighborhood")}
          </p>
        </div>
      )}
    </div>
  );
};

export default FairPriceCheck;
