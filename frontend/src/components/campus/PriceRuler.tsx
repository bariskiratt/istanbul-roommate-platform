import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n";

interface PriceRulerProps {
  low: number;
  mid: number;
  high: number;
  /** İstenen fiyat; yoksa yalnızca adil aralık çizilir. */
  asking?: number | null;
  className?: string;
}

/**
 * Adil fiyat cetveli: yeşil bant modelin adil aralığı, ince çizgi orta
 * değer, mürekkep iğne istenen fiyat. İlan kartı, ilan verme formu ve ana
 * sayfadaki örnek aynı cetveli kullanır; okuyan bir kez öğrenir.
 */
const PriceRuler = ({ low, mid, high, asking, className }: PriceRulerProps) => {
  const { n } = useI18n();
  // Ölçek bant ile istenen fiyatı birlikte kapsar; yoksa aralık dışındaki
  // fiyat cetvelden taşardı.
  const lo = asking != null ? Math.min(low, asking) : low;
  const hi = asking != null ? Math.max(high, asking) : high;
  const pad = (hi - lo) * 0.18 || hi * 0.1;
  const min = lo - pad;
  const span = hi + pad - min;
  const pos = (v: number) => `${((v - min) / span) * 100}%`;

  return (
    <div className={cn("relative h-14", className)} aria-hidden="true">
      <div className="absolute inset-x-0 top-6 h-px bg-foreground/30" />
      <div
        className="absolute top-3.5 h-5 rounded-sm bg-accent/15 border border-accent/50"
        style={{ left: pos(low), width: `calc(${pos(high)} - ${pos(low)})` }}
      />
      <div className="absolute top-3 h-6 w-px bg-accent" style={{ left: pos(mid) }} />
      {asking != null && (
        <div className="absolute top-0 -translate-x-1/2 flex flex-col items-center" style={{ left: pos(asking) }}>
          <span className="w-3 h-3 rounded-full bg-foreground border-2 border-card" />
          <span className="w-0.5 h-5 bg-foreground" />
        </div>
      )}
      <span className="absolute bottom-0 -translate-x-1/2 text-[11px] text-muted-foreground" style={{ left: pos(low) }}>
        {n(low)}
      </span>
      <span className="absolute bottom-0 -translate-x-1/2 text-[11px] text-muted-foreground" style={{ left: pos(high) }}>
        {n(high)}
      </span>
    </div>
  );
};

export default PriceRuler;
