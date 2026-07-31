import { useQuery } from "@tanstack/react-query";
import { Sparkles, TrendingUp, TrendingDown, Check, Users } from "lucide-react";
import { fetchListingFairPrice } from "@/lib/api";
import { useI18n } from "@/i18n";
import type { TranslationKey } from "@/i18n/translations";

const STYLES = {
  // cls: açık zemin üstünde (panel), solid: fotoğraf üstünde (kart)
  fair: {
    cls: "bg-accent/15 text-accent border-accent/30",
    solid: "bg-accent text-accent-foreground",
    Icon: Check,
    labelKey: "fair.fair" as TranslationKey,
  },
  above: {
    cls: "bg-destructive/15 text-destructive border-destructive/30",
    solid: "bg-destructive text-destructive-foreground",
    Icon: TrendingUp,
    labelKey: "fair.above" as TranslationKey,
  },
  below: {
    cls: "bg-secondary/15 text-secondary border-secondary/30",
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
    // Fotoğraf üstünde yarı saydam renk okunmuyordu; dolu zemin kullanılır.
    return (
      <span
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold ${
          onPhoto ? `${s.solid} shadow-sm` : `border backdrop-blur-sm ${s.cls}`
        }`}
      >
        <s.Icon className="w-3 h-3" />
        {label} · {sign}{data.deviation_pct}%
      </span>
    );
  }

  const areas = data.shared_areas
    .map(a => (lang === "en" ? AREA_EN[a] ?? a.toLowerCase() : a.toLowerCase()))
    .join(", ");

  return (
    <div className={`rounded-xl border p-3 space-y-2 ${s.cls}`}>
      <div className="flex items-center gap-2 text-sm font-semibold">
        <Sparkles className="w-4 h-4" />
        {t("fair.title")}
      </div>
      <p className="text-sm">
        <span className="font-bold">{label}.</span>{" "}
        {t("fair.body", {
          low: n(data.room_low),
          high: n(data.room_high),
          mid: n(data.room_mid),
          asking: n(data.asking_price),
          sign,
          dev: data.deviation_pct,
        })}
      </p>
      <p className="text-[11px] opacity-80 flex items-start gap-1.5">
        <Users className="w-3.5 h-3.5 mt-px flex-shrink-0" />
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
      <p className="text-[10px] opacity-70">
        {t("fair.footnote", { err: data.median_error_pct })}
      </p>
    </div>
  );
};

export default FairPriceBadge;
