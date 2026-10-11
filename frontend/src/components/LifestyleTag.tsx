import { Cigarette, Dog, Wine, Moon, Sun, Clock } from "lucide-react";
import { useI18n } from "@/i18n";
import type { TranslationKey } from "@/i18n/translations";

interface LifestyleTagProps {
  type: "smoking" | "pets" | "alcohol" | "sleep";
  value: boolean | string;
  compact?: boolean;
}

const config: Record<
  "smoking" | "pets" | "alcohol" | "sleep",
  { icon: typeof Cigarette; trueKey: TranslationKey; falseKey: TranslationKey }
> = {
  smoking: { icon: Cigarette, trueKey: "tag.smokes", falseKey: "tag.noSmoke" },
  pets: { icon: Dog, trueKey: "tag.pets", falseKey: "tag.noPets" },
  alcohol: { icon: Wine, trueKey: "tag.alcohol", falseKey: "tag.noAlcohol" },
  sleep: { icon: Moon, trueKey: "tag.flexible", falseKey: "tag.flexible" },
};

const sleepLabels: Record<string, { key: TranslationKey; Icon: typeof Moon }> = {
  erken: { key: "tag.early", Icon: Sun },
  gece: { key: "tag.night", Icon: Moon },
  esnek: { key: "tag.flexible", Icon: Clock },
};

// Yaşam tarzı bir gerçek, bir not değil: "içer" ile "içmez" aynı görünür.
// Eskiden "evet" yeşil, "hayır" mor basılıyordu; renk yargı gibi okunuyordu.
const PILL =
  "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[13px] font-medium border border-border bg-card text-foreground";

const LifestyleTag = ({ type, value, compact = false }: LifestyleTagProps) => {
  const { t } = useI18n();

  if (type === "sleep" && typeof value === "string") {
    const sleep = sleepLabels[value] || sleepLabels.esnek;
    return (
      <span className={PILL}>
        <sleep.Icon className="w-3.5 h-3.5" />
        {!compact && t(sleep.key)}
      </span>
    );
  }

  const cfg = config[type];
  const Icon = cfg.icon;
  const isTrue = Boolean(value);

  return (
    <span className={PILL}>
      <Icon className="w-3.5 h-3.5" />
      {!compact && t(isTrue ? cfg.trueKey : cfg.falseKey)}
    </span>
  );
};

export default LifestyleTag;
