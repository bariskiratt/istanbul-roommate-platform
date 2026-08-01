import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FALLBACK_DISTRICTS } from "@/lib/districts";
import { Check, ChevronDown, Search } from "lucide-react";
import { fetchLocations } from "@/lib/api";
import { filterByQuery } from "@/lib/search";
import { useI18n } from "@/i18n";

/** Seçilen konum. `neighborhood` boş dize = mahalle seçilmedi. */
export interface LocationValue {
  district: string;
  neighborhood: string;
}

interface Props {
  value: LocationValue;
  onChange: (value: LocationValue) => void;
  /** true ise yalnızca ilçe seçilir; mahalle alanı hiç gösterilmez. */
  districtOnly?: boolean;
}

interface MenuProps {
  label: string;
  /** Seçim yokken düğmede görünen metin. */
  placeholder: string;
  searchPlaceholder: string;
  items: string[];
  value: string;
  onSelect: (item: string) => void;
  disabled?: boolean;
  disabledHint?: string;
  loading?: boolean;
  loadFailed?: boolean;
  onRetry?: () => void;
  noMatchText: string;
  /** Verilirse listenin başına seçimi temizleyen bir satır konur. */
  clearLabel?: string;
}

/**
 * Aranabilir tek seçimli açılır liste. Klavye: yazarak süz, ↑/↓ ile gez,
 * Enter ile seç, Esc ile kapat (odak düğmeye döner).
 */
const SearchableMenu = ({
  label,
  placeholder,
  searchPlaceholder,
  items,
  value,
  onSelect,
  disabled,
  disabledHint,
  loading,
  loadFailed,
  onRetry,
  noMatchText,
  clearLabel,
}: MenuProps) => {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Türkçe karaktersiz arama: "besiktas" -> Beşiktaş (bkz. lib/search.ts).
  const filtered = useMemo(() => filterByQuery(items, query, i => i), [items, query]);

  // "Seçimi temizle" satırı listenin başında yer alır; klavye gezinmesi de
  // onu bir seçenek sayabilsin diye tek bir diziye alınır (boş dize = temizle).
  const options = useMemo(
    () => (clearLabel && !query ? ["", ...filtered] : filtered),
    [clearLabel, query, filtered],
  );

  const close = (focusTrigger = true) => {
    setOpen(false);
    setQuery("");
    setActive(0);
    if (focusTrigger) triggerRef.current?.focus();
  };

  // Dışarı tıklama menüyü kapatır (odağı geri almadan — kullanıcı başka yere gitti).
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: MouseEvent | TouchEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) close(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("touchstart", onPointerDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("touchstart", onPointerDown);
    };
  }, [open]);

  // Uzun listede klavyeyle gezerken etkin satır görünürde kalsın.
  useEffect(() => {
    if (!open) return;
    const node = listRef.current?.querySelector<HTMLElement>(`[data-index="${active}"]`);
    node?.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  const pick = (item: string) => {
    onSelect(item);
    close();
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      close();
      return;
    }
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (options.length === 0) return;
      const delta = e.key === "ArrowDown" ? 1 : -1;
      setActive(i => (i + delta + options.length) % options.length);
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      if (options.length > 0) pick(options[Math.min(active, options.length - 1)]);
      return;
    }
    if (e.key === "Tab") close(false);
  };

  // "Yüklenemedi + tekrar dene" yalnızca veriyi kendisi çeken menüde anlamlı.
  // Mahalle menüsünde liste boşsa bu bir ağ hatası değil, veri durumudur.
  const showEmptyState = Boolean(onRetry) && (loadFailed || (!loading && items.length === 0));

  return (
    <div className="space-y-2" ref={rootRef}>
      <label className="text-sm font-medium text-foreground">{label}</label>
      <div className="relative">
        <button
          ref={triggerRef}
          type="button"
          disabled={disabled}
          aria-haspopup="listbox"
          aria-expanded={open}
          onClick={() => {
            setActive(0);
            setOpen(o => !o);
          }}
          onKeyDown={e => {
            // Kapalıyken ↓ menüyü açsın — fare olmadan da ulaşılabilir olsun.
            if (!open && (e.key === "ArrowDown" || e.key === "Enter" || e.key === " ")) {
              e.preventDefault();
              setActive(0);
              setOpen(true);
            }
          }}
          className="w-full h-14 px-4 rounded-2xl bg-card border border-border text-left flex items-center justify-between hover:border-primary/40 transition-colors disabled:opacity-50 disabled:hover:border-border"
        >
          <span className={value ? "text-foreground" : "text-muted-foreground"}>
            {value || (disabled && disabledHint ? disabledHint : placeholder)}
          </span>
          <ChevronDown
            className={`w-4 h-4 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`}
          />
        </button>

        {open && (
          <div className="absolute z-50 mt-2 w-full rounded-2xl bg-card border border-border shadow-xl overflow-hidden">
            <div className="relative border-b border-border">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                autoFocus
                value={query}
                onChange={e => {
                  setQuery(e.target.value);
                  setActive(0);
                }}
                onKeyDown={onKeyDown}
                placeholder={searchPlaceholder}
                className="w-full h-12 pl-9 pr-3 bg-transparent text-sm outline-none text-foreground placeholder:text-muted-foreground"
              />
            </div>

            <div ref={listRef} role="listbox" className="max-h-64 overflow-y-auto py-1">
              {loading && (
                <p className="px-4 py-6 text-sm text-muted-foreground text-center">
                  {t("loc.loading")}
                </p>
              )}
              {showEmptyState && (
                <div className="px-4 py-6 text-center space-y-2">
                  <p className="text-sm text-muted-foreground">{t("loc.loadFailed")}</p>
                  {onRetry && (
                    <button
                      type="button"
                      onClick={() => onRetry()}
                      className="text-sm font-semibold text-primary hover:underline"
                    >
                      {t("common.retry")}
                    </button>
                  )}
                </div>
              )}
              {!loading && !showEmptyState && options.length === 0 && (
                <p className="px-4 py-6 text-sm text-muted-foreground text-center">
                  {noMatchText}
                </p>
              )}
              {options.map((item, index) => {
                const selected = item === value;
                return (
                  <button
                    key={item || "__clear__"}
                    type="button"
                    role="option"
                    aria-selected={selected}
                    data-index={index}
                    onMouseEnter={() => setActive(index)}
                    onClick={() => pick(item)}
                    className={`w-full text-left px-4 py-2.5 text-sm flex items-center justify-between transition-colors ${
                      index === active ? "bg-muted" : ""
                    } ${
                      selected
                        ? "text-primary font-semibold"
                        : item
                          ? "text-foreground"
                          : "text-muted-foreground"
                    }`}
                  >
                    {item || clearLabel}
                    {selected && item && <Check className="w-4 h-4" />}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

/**
 * Konum seçici: ilçe (zorunlu) + mahalle (isteğe bağlı). Liste sabit değildir,
 * /api/locations'tan gelir — tek doğruluk kaynağı sunucudadır.
 *
 * İlçe değişince mahalle seçimi düşer; başka ilçenin mahallesi kalmasın.
 */
const LocationPicker = ({ value, onChange, districtOnly }: Props) => {
  const { t } = useI18n();

  const { data: locations = [], isLoading, isError, refetch } = useQuery({
    queryKey: ["locations"],
    queryFn: fetchLocations,
    staleTime: 24 * 60 * 60 * 1000,
    retry: 2,
  });

  // Uç düştüğünde akış tıkanmasın: yedek ilçe listesiyle devam edilir,
  // mahalle seçilemez (bkz. src/lib/districts.ts).
  const districts = useMemo(
    () => (locations.length > 0 ? locations.map(l => l.district) : [...FALLBACK_DISTRICTS]),
    [locations],
  );
  const neighborhoods = useMemo(
    () => locations.find(l => l.district === value.district)?.neighborhoods ?? [],
    [locations, value.district],
  );

  return (
    <div className="space-y-4">
      <SearchableMenu
        label={t("loc.districtLabel")}
        placeholder={t("loc.districtSelect")}
        searchPlaceholder={t("loc.districtSearch")}
        items={districts}
        value={value.district}
        onSelect={district => onChange({ district, neighborhood: "" })}
        loading={isLoading}
        // Yedek liste devrede olduğu için ilçe menüsü hata durumunda da
        // dolu: kullanıcıyı boş bir ekranda bırakmak yerine devam ettiriyoruz.
        loadFailed={false}
        noMatchText={t("loc.noDistrictMatch")}
      />

      {/* Uç düştüğünde ne kaybedildiği açıkça söylenir: ilçe seçilebilir,
          mahalle seçilemez, dolayısıyla tahmin ilçe geneline dayanır. */}
      {isError && (
        <div className="flex items-start gap-2 text-xs text-muted-foreground">
          <span className="flex-1 leading-relaxed">{t("loc.fallbackNotice")}</span>
          <button
            type="button"
            onClick={() => refetch()}
            className="font-semibold text-primary hover:underline shrink-0"
          >
            {t("common.retry")}
          </button>
        </div>
      )}

      {!districtOnly && (
        <div className="space-y-2">
          <SearchableMenu
            label={t("loc.neighborhoodLabel")}
            placeholder={t("loc.neighborhoodSelect")}
            searchPlaceholder={t("loc.neighborhoodSearch")}
            items={neighborhoods}
            value={value.neighborhood}
            onSelect={neighborhood => onChange({ ...value, neighborhood })}
            disabled={!value.district}
            disabledHint={t("loc.pickDistrictFirst")}
            noMatchText={t("loc.noNeighborhoodMatch")}
            clearLabel={t("loc.neighborhoodNone")}
          />
          <p className="text-xs text-muted-foreground leading-relaxed">
            {t("loc.neighborhoodHint")}
          </p>
        </div>
      )}
    </div>
  );
};

export default LocationPicker;
