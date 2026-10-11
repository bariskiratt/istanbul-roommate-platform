import { useI18n } from "@/i18n";

// Elle çizilmiş gibi birkaç mahalle: boğazın iki yakası. Gerçek harita
// değil; bütçe haritasının ne yaptığını anlatan bir kroki. Renkler haritadaki
// anlamla aynı: yeşil bütçene uyar, sarı sınırda, kırmızı üstünde.
const PATCHES: { d: string; tone: "fit" | "edge" | "over" }[] = [
  { d: "M40 70 L92 52 L118 88 L84 118 L44 106 Z", tone: "fit" },
  { d: "M92 52 L150 44 L166 82 L118 88 Z", tone: "edge" },
  { d: "M118 88 L166 82 L176 128 L132 146 L84 118 Z", tone: "over" },
  { d: "M44 106 L84 118 L132 146 L118 186 L60 176 Z", tone: "fit" },
  { d: "M132 146 L176 128 L190 172 L150 204 L118 186 Z", tone: "edge" },
  { d: "M60 176 L118 186 L150 204 L134 236 L70 228 Z", tone: "fit" },
  { d: "M244 40 L300 36 L318 76 L268 92 L236 72 Z", tone: "edge" },
  { d: "M268 92 L318 76 L354 104 L330 142 L280 134 Z", tone: "fit" },
  { d: "M236 72 L268 92 L280 134 L240 150 L222 110 Z", tone: "over" },
  { d: "M240 150 L280 134 L330 142 L322 190 L262 196 Z", tone: "fit" },
  { d: "M222 110 L240 150 L262 196 L232 222 L206 170 Z", tone: "edge" },
  { d: "M262 196 L322 190 L340 230 L284 244 L232 222 Z", tone: "fit" },
];

const TONE = {
  fit: "fill-accent/70",
  edge: "fill-highlighter",
  over: "fill-destructive/70",
};

const MapSketch = () => {
  const { t } = useI18n();
  return (
    <div className="absolute inset-0 flex flex-col">
      <svg viewBox="0 0 400 270" className="flex-1 w-full" role="img" aria-label={t("landing.mapSketchAlt")}>
        {/* Boğaz: kuzeyden güneye kıvrılan su */}
        <path
          d="M200 0 C 186 40, 214 70, 196 110 S 180 170, 204 210 S 196 250, 210 270 L 228 270 C 214 250, 222 210, 214 190 S 206 140, 216 110 S 214 40, 222 0 Z"
          className="fill-secondary/20"
        />
        {PATCHES.map((p, i) => (
          <path key={i} d={p.d} className={`${TONE[p.tone]} stroke-card`} strokeWidth={3} strokeLinejoin="round" />
        ))}
      </svg>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 px-5 pb-4 text-[12px] text-muted-foreground">
        <li className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-accent/70" />{t("landing.mapFits")}</li>
        <li className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-highlighter" />{t("landing.mapEdge")}</li>
        <li className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-destructive/70" />{t("landing.mapOver")}</li>
      </ul>
    </div>
  );
};

export default MapSketch;
