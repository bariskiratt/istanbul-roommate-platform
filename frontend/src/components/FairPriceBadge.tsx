import { useQuery } from "@tanstack/react-query";
import { TrendingUp, TrendingDown, Check, Users } from "lucide-react";
import { fetchListingFairPrice } from "@/lib/api";
import PriceRuler from "@/components/campus/PriceRuler";
import { useI18n } from "@/i18n";
import type { TranslationKey } from "@/i18n/translations";

// Renkler kalem renkleri: adil = öğretmenin yeşili, üstünde = kırmızı kalem,
// altında = tükenmez mavisi (kiracı için iyi haber, ama "adil" değil).
const STYLES = {
  // text: kâğıt üstünde, solid: fotoğraf üstünde
  fair: {
    text: "text-accent",
    solid: "bg-accent text-accent-foreground",
    Icon: Check,
    labelKey: "fair.fair" as TranslationKey,
  },
  above: {
    text: "text-destructive",
    solid: "bg-destructive text-destructive-foreground",
    Icon: TrendingUp,
    labelKey: "fair.above" as TranslationKey,
  },
  below: {
    text: "text-secondary",
    solid: "bg-secondary text-secondary-foreground",
    Icon: TrendingDown,
    labelKey: "fair.below" as TranslationKey,
  },
} as const;

// API ortak alanları Türkçe döner; İngilizce arayüzde çevrilir.
const AREA_EN: Record<string, string> = {
  Salon: "living room",
  Mutfak: "kitchen",
  Banyo: "bathroom",
};

interface FairPriceBadgeProps {
  listingId: number;
  /** Rozet yerine ayrıntılı analiz panelini basar. */
  detailed?: boolean;
  /** Fotoğraf üstünde kullanılıyorsa dolu renk + beyaz metin (kontrast). */
  onPhoto?: boolean;
}

/**
 * İlanın istediği oda payını modelin adil aralığıyla kıyaslayan rozet.
 * Sadece ev ilanlarında anlamlı (kişisel ilanlarda kira yok).
 */
const FairPriceBadge = ({ listingId, detailed = false, onPhoto = false }: FairPriceBadgeProps) => {
  const { t, n, lang } = useI18n();
  const { data, isError } = useQuery({
    queryKey: ["fair-price", listingId],
    queryFn: () => fetchListingFairPrice(listingId),
    staleTime: 60 * 60 * 1000,
    retry: false,
  });

  if (isError || !data) return null;

  const s = STYLES[data.verdict];
  const sign = data.deviation_pct > 0 ? "+" : "";
  const label = t(s.labelKey);

  if (!detailed) {
    return (
      <span
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[12px] font-semibold ${
          onPhoto ? s.solid : `bg-card border border-border ${s.text}`
        }`}
      >
        <s.Icon className="w-3.5 h-3.5" />
        {label}
        <span className="tabular-nums font-normal opacity-90">{sign}{data.deviation_pct}%</span>
      </span>
    );
  }

  const areas = data.shared_areas
    .map(a => (lang === "en" ? AREA_EN[a] ?? a.toLowerCase() : a.toLowerCase()))
    .join(", ");

  // Model hesabı kareli kâğıtta durur: öğrencinin yazdığı metinden ayrılsın.
  return (
    <div className="paper-grid rounded-xl border border-border p-4 space-y-3 text-foreground">
      <div className="flex items-baseline justify-between gap-3">
        <h4 className="font-display text-lg font-semibold">{t("fair.title")}</h4>
        <span className={`text-sm font-semibold inline-flex items-center gap-1 ${s.text}`}>
          <s.Icon className="w-4 h-4" />
          {label}
        </span>
      </div>

      <PriceRuler low={data.room_low} mid={data.room_mid} high={data.room_high} asking={data.asking_price} />

      <p className="text-sm leading-relaxed">
        {t("fair.body", {
          low: n(data.room_low),
          high: n(data.room_high),
          mid: n(data.room_mid),
          asking: n(data.asking_price),
          sign,
          dev: data.deviation_pct,
        })}
      </p>
      <p className="text-[12px] text-muted-foreground flex items-start gap-1.5">
        <Users className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
        <span>
          {t("fair.shared", {
            bedrooms: data.bedrooms,
            occupants: data.occupants,
            areas,
            flatLow: n(data.flat_low),
            flatHigh: n(data.flat_high),
          })}
        </span>
      </p>
      <p className="text-[11px] text-muted-foreground">
        {t(data.indexed ? "fair.footnote" : "fair.footnoteNotIndexed", {
          err: data.median_error_pct,
          period: data.data_period,
        })}
      </p>
    </div>
  );
};

export default FairPriceBadge;
