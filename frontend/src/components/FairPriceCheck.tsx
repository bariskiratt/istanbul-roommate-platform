import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Sparkles, TrendingUp, TrendingDown, Check } from "lucide-react";
import {
  estimatePrice,
  fetchLocations,
  type EstimateResponse,
} from "@/lib/api";

const fmt = new Intl.NumberFormat("tr-TR");

interface Props {
  district: string;
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
  fair: { cls: "bg-green-500/10 border-green-500/40 text-foreground", icon: Check, label: "Bu kira adil aralıkta." },
  above: { cls: "bg-red-500/10 border-red-500/40 text-foreground", icon: TrendingUp, label: "Bu kira adil aralığın üzerinde." },
  below: { cls: "bg-yellow-500/10 border-yellow-500/40 text-foreground", icon: TrendingDown, label: "Bu kira adil aralığın altında." },
} as const;

/**
 * Adil fiyat danışmanı: ilçe + birkaç ek özellikten, backend'deki ML modelini
 * (/api/estimate) kullanarak adil kira aralığını gösterir ve ilan verenin
 * istediği kirayı bu bantla karşılaştırır.
 */
const FairPriceCheck = ({ district, askingPrice, roomCount }: Props) => {
  const [neighborhoods, setNeighborhoods] = useState<string[]>([]);
  const [neighborhood, setNeighborhood] = useState("");
  const [area, setArea] = useState("90");
  const [age, setAge] = useState("15");
  const [floor, setFloor] = useState("3");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<EstimateResponse | null>(null);

  // İlçe seçilince o ilçenin mahallelerini yükle.
  useEffect(() => {
    let active = true;
    setResult(null);
    setError("");
    if (!district) return;
    fetchLocations()
      .then((locs) => {
        if (!active) return;
        const list = locs[district] ?? [];
        setNeighborhoods(list);
        setNeighborhood(list[0] ?? "");
      })
      .catch(() => {
        if (active) setError("Model sunucusuna bağlanılamadı (backend çalışıyor mu?).");
      });
    return () => {
      active = false;
    };
  }, [district]);

  const analyze = async () => {
    setLoading(true);
    setError("");
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
      });
      setResult(res);
    } catch (e) {
      setError((e as Error).message);
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
          <h3 className="font-bold text-foreground">Adil Fiyat Danışmanı</h3>
          <p className="text-xs text-muted-foreground">
            Yapay zeka modeli, kiranın piyasaya uygun olup olmadığını söyler
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="col-span-2 space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground">Mahalle</label>
          <select
            value={neighborhood}
            onChange={(e) => setNeighborhood(e.target.value)}
            className="w-full h-11 rounded-xl bg-card border border-border px-3 text-sm outline-none focus:ring-2 focus:ring-primary/20"
          >
            {neighborhoods.length === 0 && <option value="">—</option>}
            {neighborhoods.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground">Alan (m²)</label>
          <Input type="number" value={area} onChange={(e) => setArea(e.target.value)} className="h-11 rounded-xl" />
        </div>
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground">Bina yaşı</label>
          <Input type="number" value={age} onChange={(e) => setAge(e.target.value)} className="h-11 rounded-xl" />
        </div>
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground">Kat</label>
          <Input type="number" value={floor} onChange={(e) => setFloor(e.target.value)} className="h-11 rounded-xl" />
        </div>
        <div className="flex items-end">
          <Button
            type="button"
            onClick={analyze}
            disabled={loading || !neighborhood}
            className="w-full h-11 rounded-xl font-semibold"
          >
            {loading ? "Hesaplanıyor…" : "Adil Fiyatı Gör"}
          </Button>
        </div>
      </div>

      {error && <p className="text-xs text-destructive">{error}</p>}

      {result && (
        <div className="space-y-3 pt-1">
          <div className="text-center">
            <div className="text-2xl font-bold tabular-nums">
              {fmt.format(result.fair_low)} – {fmt.format(result.fair_high)} ₺
            </div>
            <div className="text-xs text-muted-foreground">
              Adil aylık kira aralığı · orta tahmin {fmt.format(result.fair_mid)} ₺
            </div>
          </div>

          {result.verdict && (() => {
            const v = verdictStyles[result.verdict];
            const Icon = v.icon;
            const sign = (result.deviation_pct ?? 0) > 0 ? "+" : "";
            return (
              <div className={`rounded-xl border px-3 py-2.5 text-sm flex items-start gap-2 ${v.cls}`}>
                <Icon className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <span>
                  {v.label} İstenen {fmt.format(result.asking_price ?? 0)} ₺, orta tahminden{" "}
                  {sign}
                  {result.deviation_pct}% farklı.
                </span>
              </div>
            );
          })()}

          <p className="text-[11px] text-muted-foreground leading-relaxed">
            Modelin geçmiş ilanlardaki medyan sapması %{result.median_error_pct}. Bu bir
            tahmindir, ekspertiz değildir.
            {!result.known_neighborhood &&
              " Bu mahalle eğitim verisinde yok; tahmin ilçe geneline dayanıyor."}
          </p>
        </div>
      )}
    </div>
  );
};

export default FairPriceCheck;
