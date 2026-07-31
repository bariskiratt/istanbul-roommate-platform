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

// Durum -> renk. Backend /api/legend ile aynı; ağ hatasında yedek olsun diye
// burada da sabit tutuluyor.
const FALLBACK_COLORS: Record<StatusKey, string> = {
  safe: "#2ecc71",
  borderline: "#f1c40f",
  expensive: "#e74c3c",
  nodata: "#95a5a6",
};

const fmt = new Intl.NumberFormat("tr-TR");

const Explore = () => {
  const navigate = useNavigate();
  const mapRef = useRef<L.Map | null>(null);
  const layersRef = useRef<L.Path[]>([]);
  const statusesRef = useRef<StatusKey[]>([]);
  const altMarkersRef = useRef<L.Marker[]>([]);
  const colorsRef = useRef<Record<StatusKey, string>>(FALLBACK_COLORS);
  const seqRef = useRef(0);

  const [budget, setBudget] = useState(25000);
  const [summary, setSummary] = useState<Record<StatusKey, number> | null>(null);
  const [status, setStatus] = useState("Harita yükleniyor…");
  const [alt, setAlt] = useState<AlternativesResponse | null>(null);

  // Harita tıklama işleyicisi mount'ta bir kez kaydedildiği için `budget`
  // state'ini kapanışta (closure) yakalar ve güncel değeri görmez. Güncel
  // bütçeyi ref üzerinden okuyoruz.
  const budgetRef = useRef(budget);
  budgetRef.current = budget;

  const styleFor = (s: StatusKey): L.PathOptions => ({
    fillColor: colorsRef.current[s] ?? FALLBACK_COLORS[s],
    fillOpacity: s === "nodata" ? 0.25 : 0.65,
    weight: 1,
    color: "#fff",
    opacity: 0.6,
  });

  // Bütçe değişince yalnızca durum listesini çek ve yeniden renklendir.
  const recolor = async (b: number) => {
    const seq = ++seqRef.current;
    try {
      const data = await fetchHeatmap(b);
      if (seq !== seqRef.current) return; // yarış: yalnızca son istek uygulanır
      statusesRef.current = data.statuses;
      layersRef.current.forEach((layer, i) => {
        if (layer) layer.setStyle(styleFor(data.statuses[i]));
      });
      setSummary(data.summary);
      const total = data.summary.safe + data.summary.borderline + data.summary.expensive;
      setStatus(`Veri bulunan ${total} mahalleden ${data.summary.safe} tanesi bütçene uygun.`);
    } catch (e) {
      setStatus(`Isı haritası alınamadı: ${(e as Error).message}`);
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
    setStatus("Alternatifler hesaplanıyor…");
    try {
      const data = await fetchAlternatives(id, budgetRef.current);
      clearAltMarkers();
      setAlt(data);
      mapRef.current?.closePopup();
      setStatus("");
      if (data.reachable) {
        const t = data.target;
        altMarkersRef.current.push(
          L.marker([t.lat, t.lon], { icon: pin("hsl(263 45% 62%)") })
            .bindTooltip(`${t.name} (hedef)`)
            .addTo(mapRef.current!),
        );
        data.recommendations.forEach((r) => {
          altMarkersRef.current.push(
            L.marker([r.lat, r.lon], { icon: pin("hsl(160 32% 52%)") })
              .bindTooltip(`${r.name} · ${fmt.format(Math.round(r.price ?? 0))} TL`)
              .addTo(mapRef.current!),
          );
        });
      }
    } catch (e) {
      setStatus(`Alternatifler alınamadı: ${(e as Error).message}`);
    }
  };

  // Haritayı bir kez kur.
  useEffect(() => {
    const map = L.map("explore-map").setView([41.02, 28.95], 10);
    mapRef.current = map;
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap katkıcıları",
      maxZoom: 18,
    }).addTo(map);

    // Popup butonuna tıklamayı delege et (popup içeriği dinamik).
    map.getContainer().addEventListener("click", (e) => {
      const btn = (e.target as HTMLElement).closest?.(".popup-alt") as HTMLElement | null;
      if (btn) runAlternatives(Number(btn.dataset.id));
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
            };
            layersRef.current[p.id] = layer as L.Path;
            layer.bindPopup(() => {
              const price =
                p.avg_price == null
                  ? "Yeterli ilan verisi yok"
                  : `${fmt.format(Math.round(p.avg_price))} TL / ay`;
              let html = `<div style="font-weight:650">${p.neighborhood || "Bilinmeyen"} Mah.</div>`;
              html += `<div style="color:#6b7280;font-size:12px;margin-bottom:6px">${p.district || ""}</div>`;
              html += `<div style="font-size:16px;font-weight:650">${price}</div>`;
              if (p.avg_price != null) {
                html += `<button class="popup-alt" data-id="${p.id}" style="margin-top:8px;width:100%;padding:7px;border:none;border-radius:6px;background:hsl(263 45% 45%);color:#fff;font-weight:600;cursor:pointer">🚇 Yakın uygun alternatifler</button>`;
              }
              return html;
            });
          },
        }).addTo(map);
        await recolor(budget);
      } catch (e) {
        setStatus(
          `Harita verisi yüklenemedi: ${(e as Error).message}. Backend çalışıyor mu? (backend/ → python -m app.main)`,
        );
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
          <h1 className="font-bold text-xl text-foreground">Bütçe Haritası</h1>
          <p className="text-xs text-muted-foreground">
            Bütçene uygun mahalleleri gör, pahalı bir semte yakın uygun alternatifleri keşfet.
          </p>
        </div>
      </div>

      {/* Bütçe kontrolü */}
      <div className="px-6 py-3 border-y border-border bg-card flex flex-wrap items-center gap-4">
        <div className="text-lg font-bold tabular-nums whitespace-nowrap">
          {fmt.format(budget)} ₺
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
          aria-label="Aylık bütçe"
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

      {status && <div className="px-6 py-2 text-xs text-muted-foreground">{status}</div>}

      {/* Harita + öneri paneli */}
      <div className="relative flex-1 min-h-[420px]">
        <div id="explore-map" className="absolute inset-0" />

        {alt && (
          <div className="absolute top-3 right-3 z-[1000] w-[320px] max-w-[calc(100%-24px)] max-h-[calc(100%-24px)] overflow-y-auto bg-card border border-border rounded-xl shadow-xl p-4">
            <button
              onClick={() => {
                setAlt(null);
                clearAltMarkers();
              }}
              className="absolute top-3 right-3 text-muted-foreground hover:text-foreground text-xl leading-none"
              aria-label="Kapat"
            >
              ×
            </button>
            <h3 className="font-semibold text-sm pr-6">{alt.target.name} Mah. yakını</h3>

            {!alt.reachable ? (
              <p className="text-xs text-muted-foreground mt-1">
                {alt.target.message ?? "Bu mahalle için ulaşım tabanlı öneri üretilemedi."}
              </p>
            ) : alt.recommendations.length === 0 ? (
              <p className="text-xs text-muted-foreground mt-1">
                Bu bütçeyle ağ üzerinde uygun alternatif bulunamadı. Bütçeyi artırmayı dene.
              </p>
            ) : (
              <>
                <p className="text-xs text-muted-foreground mt-0.5 mb-1">
                  Bütçe {fmt.format(alt.budget ?? budget)} ₺ · raylı sistemle ulaşılabilir{" "}
                  {alt.recommendations.length} uygun mahalle
                </p>
                {alt.recommendations.map((r, i) => (
                  <div
                    key={r.id}
                    onClick={() => mapRef.current?.flyTo([r.lat, r.lon], 14)}
                    className="py-2.5 border-t border-border cursor-pointer hover:opacity-80"
                  >
                    <div className="text-sm font-semibold flex items-center gap-2">
                      <span>
                        {i + 1}. {r.name} Mah.
                      </span>
                      <span className="text-[11px] font-semibold px-1.5 py-0.5 rounded-full bg-primary text-primary-foreground">
                        {r.network_cost} durak
                      </span>
                    </div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      <span className="font-semibold text-foreground">
                        {fmt.format(Math.round(r.price ?? 0))} ₺
                      </span>
                      {r.district ? ` · ${r.district}` : ""}
                      {r.saving != null && r.saving > 0 ? (
                        <span className="text-accent">
                          {" "}
                          · {fmt.format(r.saving)} ₺ ucuz
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
