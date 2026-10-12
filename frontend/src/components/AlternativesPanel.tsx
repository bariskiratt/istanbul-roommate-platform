import type { AlternativesResponse } from "@/lib/api";
import { altListed, altPanelState, routeParts } from "@/lib/alternatives";
import { useI18n } from "@/i18n";

type Props = {
  /** Yanıt gelene kadar null; o sırada "hesaplanıyor" gösterilir. */
  data: AlternativesResponse | null;
  error: string | null;
  onClose: () => void;
  /** Listede bir satıra dokunulunca harita o mahalleye uçar. */
  onPick: (lat: number, lon: number) => void;
};

/**
 * Haritada bir mahallenin balonundaki "Yakında daha ucuzu" düğmesinin açtığı
 * liste. Numaralar haritadaki iğnelerle aynı sırada.
 */
const AlternativesPanel = ({ data, error, onClose, onPick }: Props) => {
  const { t, n: fmtNum } = useI18n();
  const state = data ? altPanelState(data) : null;
  const listed = data ? altListed(data) : [];

  return (
    // Telefonda alttan açılan yarım sayfa (haritanın üstü ve iğneler görünür
    // kalsın), geniş ekranda sağ üstte sabit genişlikte kart.
    <div className="absolute inset-x-3 bottom-3 max-h-[55%] sm:inset-x-auto sm:bottom-auto sm:top-3 sm:right-3 sm:w-[340px] sm:max-h-[calc(100%-24px)] z-[1000] overflow-y-auto bg-card text-card-foreground border border-border rounded-xl shadow-xl p-4">
      <button
        onClick={onClose}
        className="absolute top-2.5 right-3 text-muted-foreground hover:text-foreground text-xl leading-none"
        aria-label={t("common.close")}
      >
        ×
      </button>

      {!data ? (
        <p className="text-[13px] text-muted-foreground pr-6" aria-live="polite">
          {error ? t("map.altFailed", { error }) : t("map.altCalculating")}
        </p>
      ) : (
        <>
          <h3 className="font-display text-[17px] font-semibold leading-tight pr-6">
            {t("map.altPanelTitle", { name: data.target.name })}
          </h3>
          {data.target.price != null && (
            <p className="text-[12px] text-muted-foreground mt-1">
              {t("map.altTargetPrice", {
                name: data.target.name,
                price: fmtNum(Math.round(data.target.price)),
              })}
              {data.target.low_confidence && ` ${t("map.altTargetLowConfidence")}`}
            </p>
          )}

          <p className="text-[13px] mt-3">
            {state === "unreachable" && t("map.altUnreachable")}
            {state === "none" && t("map.altNone", { max: data.max_minutes })}
            {state === "over_budget" && t("map.altNoneInBudget")}
            {state === "fits" &&
              t("map.altRule", { max: data.max_minutes, budget: fmtNum(data.budget) })}
          </p>

          {listed.length > 0 && (
            <ol className="mt-2">
              {listed.map((c, i) => (
                <li key={c.id}>
                  <button
                    type="button"
                    onClick={() => onPick(c.lat, c.lon)}
                    className="w-full text-left flex gap-3 py-2.5 border-t border-border hover:bg-muted/60 transition-colors"
                  >
                    <span className="mt-0.5 w-[22px] h-[22px] shrink-0 rounded-full bg-primary text-primary-foreground text-[11px] font-bold flex items-center justify-center">
                      {i + 1}
                    </span>
                    <span className="flex-1 min-w-0">
                      <span className="flex items-baseline justify-between gap-2">
                        <span className="text-[14px] font-semibold truncate">
                          {t("map.altItem", { name: c.name })}
                        </span>
                        <span className="text-[13px] font-semibold whitespace-nowrap">
                          {t("map.altMinutes", { count: c.minutes })}
                        </span>
                      </span>
                      <span className="block text-[12px] text-muted-foreground mt-0.5">
                        <span className="font-semibold text-foreground">
                          {fmtNum(Math.round(c.price))} {t("common.currency")}
                        </span>
                        {c.district ? ` · ${c.district}` : ""}
                        {c.status === "borderline" && (
                          <span className="ml-1.5 px-1.5 rounded bg-highlighter text-highlighter-foreground font-semibold">
                            {t("map.altBorderline")}
                          </span>
                        )}
                        {c.low_confidence && (
                          <span className="ml-1.5 px-1.5 rounded border border-dashed border-muted-foreground/60">
                            {t("map.altLowConfidence")}
                          </span>
                        )}
                      </span>
                      {c.over_budget != null && (
                        <span className="block text-[12px] font-semibold text-destructive mt-0.5">
                          {t("map.altOverBudget", { amount: fmtNum(c.over_budget) })}
                        </span>
                      )}
                      <span className="block text-[12px] text-muted-foreground mt-0.5">
                        {routeParts(c)
                          .map((part) => t(part.key, part.vars))
                          .join(" · ")}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ol>
          )}

          {state !== "unreachable" && (
            <p className="text-[11px] text-muted-foreground mt-3 pt-2 border-t border-border">
              {t("map.altFootnote")}
            </p>
          )}
        </>
      )}
    </div>
  );
};

export default AlternativesPanel;
