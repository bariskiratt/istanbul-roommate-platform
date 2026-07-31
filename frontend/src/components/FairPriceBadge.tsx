import { useQuery } from "@tanstack/react-query";
import { Sparkles, TrendingUp, TrendingDown, Check, Users } from "lucide-react";
import { fetchListingFairPrice } from "@/lib/api";

const fmt = new Intl.NumberFormat("tr-TR");

const STYLES = {
  fair: { cls: "bg-accent/15 text-accent border-accent/30", Icon: Check, label: "Adil fiyat" },
  above: { cls: "bg-destructive/15 text-destructive border-destructive/30", Icon: TrendingUp, label: "Piyasanın üstünde" },
  below: { cls: "bg-secondary/15 text-secondary border-secondary/30", Icon: TrendingDown, label: "Piyasanın altında" },
} as const;

/**
 * İlanın istediği oda payını modelin adil aralığıyla kıyaslayan rozet.
 * Sadece ev ilanlarında anlamlı (kişisel ilanlarda kira yok).
 */
const FairPriceBadge = ({ listingId, detailed = false }: { listingId: number; detailed?: boolean }) => {
  const { data, isError } = useQuery({
    queryKey: ["fair-price", listingId],
    queryFn: () => fetchListingFairPrice(listingId),
    staleTime: 60 * 60 * 1000,
    retry: false,
  });

  if (isError || !data) return null;

  const s = STYLES[data.verdict];
  const sign = data.deviation_pct > 0 ? "+" : "";

  if (!detailed) {
    return (
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border backdrop-blur-sm ${s.cls}`}>
        <s.Icon className="w-3 h-3" />
        {s.label} · {sign}{data.deviation_pct}%
      </span>
    );
  }

  return (
    <div className={`rounded-xl border p-3 space-y-2 ${s.cls}`}>
      <div className="flex items-center gap-2 text-sm font-semibold">
        <Sparkles className="w-4 h-4" />
        Adil Fiyat Analizi
      </div>
      <p className="text-sm">
        <span className="font-bold">{s.label}.</span> Bu oda için adil aralık{" "}
        <span className="font-bold tabular-nums">
          {fmt.format(data.room_low)} – {fmt.format(data.room_high)} ₺
        </span>{" "}
        (orta {fmt.format(data.room_mid)} ₺); istenen {fmt.format(data.asking_price)} ₺,
        yani {sign}{data.deviation_pct}% farklı.
      </p>
      <p className="text-[11px] opacity-80 flex items-start gap-1.5">
        <Users className="w-3.5 h-3.5 mt-px flex-shrink-0" />
        <span>
          {data.bedrooms} yatak odası = {data.occupants} kişi; {data.shared_areas.join(", ").toLowerCase()} ortak
          kullanılıyor. Daire geneli {fmt.format(data.flat_low)}–{fmt.format(data.flat_high)} ₺,
          kişi payı bu sayının {data.occupants}'e bölünmüşü.
        </span>
      </p>
      <p className="text-[10px] opacity-70">
        İlçe geneli tahmin · model medyan sapması %{data.median_error_pct} · TÜFE ile güncellendi
      </p>
    </div>
  );
};

export default FairPriceBadge;
