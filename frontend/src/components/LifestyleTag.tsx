import { Cigarette, Dog, Wine, Moon, Sun, Clock } from "lucide-react";

interface LifestyleTagProps {
  type: "smoking" | "pets" | "alcohol" | "sleep";
  value: boolean | string;
  compact?: boolean;
}

const config = {
  smoking: {
    icon: Cigarette,
    trueLabel: "Sigara içer",
    falseLabel: "Sigara içmez",
  },
  pets: {
    icon: Dog,
    trueLabel: "Hayvan dostu",
    falseLabel: "Hayvansız",
  },
  alcohol: {
    icon: Wine,
    trueLabel: "Alkol kullanır",
    falseLabel: "Alkol kullanmaz",
  },
  sleep: {
    icon: Moon,
    trueLabel: "",
    falseLabel: "",
  },
};

const sleepLabels: Record<string, { label: string; Icon: typeof Moon }> = {
  erken: { label: "Erken kalkar", Icon: Sun },
  gece: { label: "Gece kuşu", Icon: Moon },
  esnek: { label: "Esnek", Icon: Clock },
};

const LifestyleTag = ({ type, value, compact = false }: LifestyleTagProps) => {
  if (type === "sleep" && typeof value === "string") {
    const sleep = sleepLabels[value] || sleepLabels.esnek;
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-lavender/40 text-foreground">
        <sleep.Icon className="w-3.5 h-3.5" />
        {!compact && sleep.label}
      </span>
    );
  }

  const cfg = config[type];
  const Icon = cfg.icon;
  const isTrue = Boolean(value);

  return (
    <span className={
      isTrue
        ? "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-mint/20 text-foreground"
        : "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-lavender/40 text-foreground"
    }>
      <Icon className="w-3.5 h-3.5" />
      {!compact && (isTrue ? cfg.trueLabel : cfg.falseLabel)}
    </span>
  );
};

export default LifestyleTag;
