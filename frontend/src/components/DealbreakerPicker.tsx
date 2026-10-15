import { Check, Cigarette, Dog, Moon, Sun, Wine } from "lucide-react";
import { useI18n } from "@/i18n";
import type { TranslationKey } from "@/i18n/translations";
import { DEALBREAKERS, toggleDealbreaker, type Dealbreaker } from "@/lib/dealbreakers";

const OPTIONS: Record<Dealbreaker, { icon: typeof Check; label: TranslationKey; desc?: TranslationKey }> = {
  smoking: { icon: Cigarette, label: "deal.smoking", desc: "deal.smokingDesc" },
  alcohol: { icon: Wine, label: "deal.alcohol" },
  pets: { icon: Dog, label: "deal.pets", desc: "deal.petsDesc" },
  night_owl: { icon: Moon, label: "deal.nightOwl" },
  early_bird: { icon: Sun, label: "deal.earlyBird" },
};

/**
 * "İstemediklerim" seçimi. Kayıtta ve profil düzenlemede aynı bileşen.
 * Hiçbir şey seçmemek geçerli bir cevaptır: eleme yok demektir.
 */
const DealbreakerPicker = ({
  value,
  onChange,
}: {
  value: Dealbreaker[];
  onChange: (next: Dealbreaker[]) => void;
}) => {
  const { t } = useI18n();
  return (
    <div className="space-y-3">
      {DEALBREAKERS.map(key => {
        const option = OPTIONS[key];
        const selected = value.includes(key);
        return (
          <button
            key={key}
            type="button"
            role="checkbox"
            aria-checked={selected}
            onClick={() => onChange(toggleDealbreaker(value, key))}
            className={`w-full flex items-center gap-4 px-4 py-3.5 rounded-xl border bg-card text-left transition-colors ${
              selected ? "border-foreground" : "border-input hover:border-foreground/40"
            }`}
          >
            <option.icon
              className={`w-5 h-5 shrink-0 ${selected ? "text-foreground" : "text-muted-foreground"}`}
              strokeWidth={1.8}
            />
            <span className="flex-1">
              <span className="block text-[15px] font-semibold text-foreground">{t(option.label)}</span>
              {option.desc && <span className="block text-xs text-muted-foreground">{t(option.desc)}</span>}
            </span>
            <span
              className={`w-6 h-6 shrink-0 rounded-md border flex items-center justify-center transition-colors ${
                selected ? "bg-foreground border-foreground text-background" : "border-input"
              }`}
            >
              {selected && <Check className="w-4 h-4" />}
            </span>
          </button>
        );
      })}
      <p className="text-xs text-muted-foreground leading-relaxed">{t("deal.mutual")}</p>
    </div>
  );
};

export default DealbreakerPicker;
