import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { ArrowLeft } from "lucide-react";
import {
  fetchAlternatives,
  fetchGeojson,
  fetchHeatmap,
  fetchLegend,
  type AlternativesResponse,
  type StatusKey,
} from "@/lib/api";
import { useI18n } from "@/i18n";
import type { TranslationKey } from "@/i18n/translations";

// Alternatif semt önerisi (raylı ağ tabanlı) şu an arayüzde KAPALI —
// çıktı kalitesi ayarlanana kadar inaktif. Backend ucu (/api/alternatives)
// ve buradaki kod duruyor; geri açmak için bu bayrağı true yap.
const ALTERNATIVES_ENABLED = false;

// Durum -> renk. Backend /api/legend ile aynı; ağ hatasında yedek olsun diye
// burada da sabit tutuluyor.
const FALLBACK_COLORS: Record<StatusKey, string> = {
  safe: "#2ecc71",
  borderline: "#f1c40f",
  expensive: "#e74c3c",
  nodata: "#95a5a6",
};

// Durum çubuğu metni: parçalar render sırasında çevrilir, böylece dil
// değiştiğinde ekrandaki metin de anında güncellenir.
type StatusPart = { key: TranslationKey; vars?: Record<string, string | number> };
type StatusMsg = StatusPart[] | null;

const Explore = () => {
  const navigate = useNavigate();
  const { t, n: fmtNum } = useI18n();
  const mapRef = useRef<L.Map | null>(null);
  const layersRef = useRef<L.Path[]>([]);
  const statusesRef = useRef<StatusKey[]>([]);
  const lowConfRef = useRef<boolean[]>([]);
  const altMarkersRef = useRef<L.Marker[]>([]);
  const colorsRef = useRef<Record<StatusKey, string>>(FALLBACK_COLORS);
  const seqRef = useRef(0);

  const [budget, setBudget] = useState(25000);
  const [summary, setSummary] = useState<Record<StatusKey, number> | null>(null);
  // Durum metni çevrilmiş dize olarak DEĞİL, anahtar + değişken olarak tutulur:
  // çevrilmiş dize saklansaydı dil değiştirildiğinde eski dilde donup kalırdı.
  const [status, setStatus] = useState<StatusMsg>([{ key: "map.loading" }]);
  const [alt, setAlt] = useState<AlternativesResponse | null>(null);

  // Harita bir kez kurulur; popup üreticileri ilk render'ın `t`/`n`'ini yakalar.
  // Dil değişince güncel çeviriyi ve sayı biçimini görebilmeleri için ref üzerinden okunur.
  const tRef = useRef(t);
  tRef.current = t;
  const fmtNumRef = useRef(fmtNum);
  fmtNumRef.current = fmtNum;

  // Harita tıklama işleyicisi mount'ta bir kez kaydedildiği için `budget`
  // state'ini kapanışta (closure) yakalar ve güncel değeri görmez. Güncel
  // bütçeyi ref üzerinden okuyoruz.
  const budgetRef = useRef(budget);
  budgetRef.current = budget;

  // Az ilana dayanan mahalleler yine renklenir (harita boş kalmasın) ama
  // soluk dolgu + kesik çizgiyle "bu tahmin zayıf" sinyali verilir.
  const styleFor = (s: StatusKey, lowConfidence = false): L.PathOptions => ({
    fillColor: colorsRef.current[s] ?? FALLBACK_COLORS[s],
    fillOpacity: s === "nodata" ? 0.25 : lowConfidence ? 0.3 : 0.65,
    weight: 1,
    color: "#fff",
    opacity: 0.6,
    dashArray: lowConfidence ? "3 3" : undefined,
  });

  // Bütçe değişince yalnızca durum listesini çek ve yeniden renklendir.
  const recolor = async (b: number) => {
    const seq = ++seqRef.current;
    try {
      const data = await fetchHeatmap(b);
      if (seq !== seqRef.current) return; // yarış: yalnızca son istek uygulanır
      statusesRef.current = data.statuses;
      lowConfRef.current = data.low_confidence ?? [];
      layersRef.current.forEach((layer, i) => {
        if (layer) layer.setStyle(styleFor(data.statuses[i], lowConfRef.current[i]));
      });
      setSummary(data.summary);
      const total = data.summary.safe + data.summary.borderline + data.summary.expensive;
      const weak = data.summary.low_confidence ?? 0;
      setStatus([
        { key: "map.summary", vars: { total, safe: data.summary.safe } },
        ...(weak ? [{ key: "map.weak" as TranslationKey, vars: { weak } }] : []),
      ]);
    } catch (e) {
      setStatus([{ key: "map.heatFailed", vars: { error: (e as Error).message } }]);
    }
  };

  const clearAltMarkers = () => {
    altMarkersRef.current.forEach((m) => mapRef.current?.removeLayer(m));
    altMarkersRef.current = [];
  };

  const pin = (color: string) =>
    L.divIcon({
      className: "",
      html: `<div style="width:14px;height:14px;border-radius:50%;background:${color};border:2px solid #fff;box-shadow:0 0 0 1px rgba(0,0,0,.3)"></div>`,
      iconSize: [14, 14],
    });

  const runAlternatives = async (id: number) => {
    setStatus([{ key: "map.altCalculating" }]);
    try {
      const data = await fetchAlternatives(id, budgetRef.current);
      clearAltMarkers();
      setAlt(data);
      mapRef.current?.closePopup();
      setStatus(null);
      if (data.reachable) {
        const target = data.target;
        altMarkersRef.current.push(
          L.marker([target.lat, target.lon], { icon: pin("hsl(263 45% 62%)") })
            .bindTooltip(tRef.current("map.altTarget", { name: target.name }))
            .addTo(mapRef.current!),
        );
        data.recommendations.forEach((r) => {
          altMarkersRef.current.push(
            L.marker([r.lat, r.lon], { icon: pin("hsl(160 32% 52%)") })
              .bindTooltip(`${r.name} · ${fmtNumRef.current(Math.round(r.price ?? 0))} TL`)
              .addTo(mapRef.current!),
          );
        });
      }
    } catch (e) {
      setStatus([{ key: "map.altFailed", vars: { error: (e as Error).message } }]);
    }
  };

  // Haritayı bir kez kur.
  useEffect(() => {
    const map = L.map("explore-map").setView([41.02, 28.95], 10);
    mapRef.current = map;
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: tRef.current("map.attribution"),
      maxZoom: 18,
    }).addTo(map);

    // Popup butonuna tıklamayı delege et (popup içeriği dinamik).
    map.getContainer().addEventListener("click", (e) => {
      const btn = (e.target as HTMLElement).closest?.(".popup-alt") as HTMLElement | null;
      if (btn && ALTERNATIVES_ENABLED) runAlternatives(Number(btn.dataset.id));
    });

    (async () => {
      try {
        const legend = await fetchLegend();
        colorsRef.current = Object.fromEntries(
          Object.entries(legend).map(([k, v]) => [k, v.color]),
        ) as Record<StatusKey, string>;
      } catch {
        /* yedek renkler kullanılır */
      }

      try {
        const geojson = await fetchGeojson();
        L.geoJSON(geojson, {
          style: () => styleFor("nodata"),
          onEachFeature: (feature, layer) => {
            const p = feature.properties as {
              id: number;
              neighborhood?: string;
              district?: string;
              avg_price?: number | null;
              listing_count?: number | null;
            };
            layersRef.current[p.id] = layer as L.Path;
            layer.bindPopup(() => {
              const price =
                p.avg_price == null
                  ? tRef.current("map.noData")
                  : `${fmtNumRef.current(Math.round(p.avg_price))} TL / ${tRef.current("map.month")}`;
              const area = p.neighborhood
                ? tRef.current("map.neighborhoodLabel", { name: p.neighborhood })
                : tRef.current("map.unknown");
              let html = `<div style="font-weight:650">${area}</div>`;
              html += `<div style="color:#6b7280;font-size:12px;margin-bottom:6px">${p.district || ""}</div>`;
              html += `<div style="font-size:16px;font-weight:650">${price}</div>`;
              if (p.avg_price != null && p.listing_count != null && p.listing_count < 8) {
                html += `<div style="color:#b48a00;font-size:11px;margin-top:4px">⚠️ ${tRef.current("map.fewListings", { count: p.listing_count })}</div>`;
              }
              if (ALTERNATIVES_ENABLED && p.avg_price != null) {
                html += `<button class="popup-alt" data-id="${p.id}" style="margin-top:8px;width:100%;padding:7px;border:none;border-radius:6px;background:hsl(263 45% 45%);color:#fff;font-weight:600;cursor:pointer">${tRef.current("map.altButton")}</button>`;
              }
              return html;
            });
          },
        }).addTo(map);
        await recolor(budget);
      } catch (e) {
        setStatus([{ key: "map.geoFailed", vars: { error: (e as Error).message } }]);
      }
    })();

    return () => {
      map.remove();
      mapRef.current = null;
      layersRef.current = [];
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <div className="px-6 pt-4 pb-3 flex items-center gap-3">
        <button
          onClick={() => navigate(-1)}
          className="w-10 h-10 rounded-full bg-card flex items-center justify-center hover:bg-muted transition-colors"
          style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="font-bold text-xl text-foreground">{t("map.title")}</h1>
          <p className="text-xs text-muted-foreground">{t("map.sub")}</p>
        </div>
      </div>

      {/* Bütçe kontrolü */}
      <div className="px-6 py-3 border-y border-border bg-card flex flex-wrap items-center gap-4">
        <div className="text-lg font-bold tabular-nums whitespace-nowrap">
          {fmtNum(budget)} ₺
        </div>
        <input
          type="range"
          min={5000}
          max={150000}
          step={1000}
          value={budget}
          onChange={(e) => {
            const v = Number(e.target.value);
            setBudget(v);
            recolor(v);
          }}
          className="flex-1 min-w-[180px] accent-primary"
          aria-label={t("map.budgetLabel")}
        />
        {summary && (
          <div className="flex flex-wrap gap-3 text-xs">
            {(["safe", "borderline", "expensive", "nodata"] as StatusKey[]).map((k) => (
              <span key={k} className="flex items-center gap-1.5">
                <i
                  className="inline-block w-3 h-3 rounded-sm"
                  style={{ background: colorsRef.current[k] ?? FALLBACK_COLORS[k] }}
                />
                {summary[k]}
              </span>
            ))}
          </div>
        )}
      </div>

      {status && status.length > 0 && (
        <div className="px-6 py-2 text-xs text-muted-foreground">
          {status.map((part) => t(part.key, part.vars)).join("")}
        </div>
      )}

      {/* Harita + öneri paneli */}
      <div className="relative flex-1 min-h-[420px]">
        <div id="explore-map" className="absolute inset-0" />

        {ALTERNATIVES_ENABLED && alt && (
          <div className="absolute top-3 right-3 z-[1000] w-[320px] max-w-[calc(100%-24px)] max-h-[calc(100%-24px)] overflow-y-auto bg-card border border-border rounded-xl shadow-xl p-4">
            <button
              onClick={() => {
                setAlt(null);
                clearAltMarkers();
              }}
              className="absolute top-3 right-3 text-muted-foreground hover:text-foreground text-xl leading-none"
              aria-label={t("common.close")}
            >
              ×
            </button>
            <h3 className="font-semibold text-sm pr-6">
              {t("map.altPanelTitle", { name: alt.target.name })}
            </h3>

            {!alt.reachable ? (
              <p className="text-xs text-muted-foreground mt-1">
                {alt.target.message ?? t("map.altUnreachable")}
              </p>
            ) : alt.recommendations.length === 0 ? (
              <p className="text-xs text-muted-foreground mt-1">{t("map.altNone")}</p>
            ) : (
              <>
                <p className="text-xs text-muted-foreground mt-0.5 mb-1">
                  {t("map.altSummary", {
                    budget: fmtNum(alt.budget ?? budget),
                    count: alt.recommendations.length,
                  })}
                </p>
                {alt.recommendations.map((r, i) => (
                  <div
                    key={r.id}
                    onClick={() => mapRef.current?.flyTo([r.lat, r.lon], 14)}
                    className="py-2.5 border-t border-border cursor-pointer hover:opacity-80"
                  >
                    <div className="text-sm font-semibold flex items-center gap-2">
                      <span>{t("map.altItem", { index: i + 1, name: r.name })}</span>
                      <span className="text-[11px] font-semibold px-1.5 py-0.5 rounded-full bg-primary text-primary-foreground">
                        {t("map.altStops", { count: r.network_cost })}
                      </span>
                    </div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      <span className="font-semibold text-foreground">
                        {fmtNum(Math.round(r.price ?? 0))} {t("common.currency")}
                      </span>
                      {r.district ? ` · ${r.district}` : ""}
                      {r.saving != null && r.saving > 0 ? (
                        <span className="text-accent">
                          {" "}
                          · {t("map.altCheaper", { amount: fmtNum(r.saving) })}
                        </span>
                      ) : null}
                    </div>
                  </div>
                ))}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default Explore;
