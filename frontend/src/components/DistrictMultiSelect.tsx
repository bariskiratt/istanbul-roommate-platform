import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Input } from "@/components/ui/input";
import { fetchLocations } from "@/lib/api";
import { filterByQuery } from "@/lib/search";
import { useI18n } from "@/i18n";

/**
 * Aramalı, çok seçimli semt (ilçe) çipleri.
 *
 * Kayıt akışı, profil düzenleme ve destedeki filtre aynı listeyi kullanır:
 * GET /api/locations. Eskiden profil düzenlemede elle yazılmış 17 semtlik
 * ayrı bir liste vardı; kayıtta seçilen 38 semtten biri (ör. Kâğıthane)
 * orada hiç görünmüyordu, kullanıcı seçimini ne görebiliyor ne
 * kaldırabiliyordu.
 *
 * Listede olmayan ama seçili gelen semt (ör. liste sonradan daralırsa) yine
 * de çip olarak gösterilir: seçim sessizce kaybolmaz, kaldırılabilir.
 *
 * Aynı queryKey ("locations") konum seçicide de kullanılıyor; istek bir
 * kez atılır.
 */
interface Props {
  selected: string[];
  onChange: (next: string[]) => void;
  /** Çip alanının en fazla yüksekliği (taşan kısım kayar). */
  maxHeightClass?: string;
}

const DistrictMultiSelect = ({ selected, onChange, maxHeightClass = "max-h-[240px]" }: Props) => {
  const { t } = useI18n();
  const [query, setQuery] = useState("");

  const {
    data: locations = [],
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["locations"],
    queryFn: fetchLocations,
    staleTime: 24 * 60 * 60 * 1000,
    retry: 2,
  });

  const options = useMemo(() => {
    const known = locations.map(l => l.district);
    const extra = selected.filter(d => !known.includes(d));
    return [...extra, ...known];
  }, [locations, selected]);

  // Türkçe karaktersiz arama ("besiktas" -> Beşiktaş), bkz. lib/search.ts.
  const visible = useMemo(() => filterByQuery(options, query, d => d), [options, query]);

  const toggle = (d: string) =>
    onChange(selected.includes(d) ? selected.filter(x => x !== d) : [...selected, d]);

  return (
    <div className="space-y-3">
      <Input
        placeholder={t("ob.districtSearch")}
        value={query}
        onChange={e => setQuery(e.target.value)}
        // Esc aramayı temizler; seçilen semtler korunur.
        onKeyDown={e => { if (e.key === "Escape") setQuery(""); }}
        className="h-11 text-[15px]"
      />
      <div className={`${maxHeightClass} overflow-y-auto pr-1`}>
        {isLoading && (
          <p className="py-4 text-sm text-muted-foreground">{t("loc.loading")}</p>
        )}
        {!isLoading && (isError || locations.length === 0) && (
          <div className="py-4 space-y-2">
            <p className="text-sm text-muted-foreground">{t("loc.loadFailed")}</p>
            <button
              type="button"
              onClick={() => refetch()}
              className="text-sm font-semibold text-secondary hover:underline"
            >
              {t("common.retry")}
            </button>
          </div>
        )}
        {options.length > 0 && visible.length === 0 && (
          <p className="py-4 text-sm text-muted-foreground">{t("loc.noDistrictMatch")}</p>
        )}
        <div className="flex flex-wrap gap-2">
          {visible.map(d => (
            <button
              key={d}
              type="button"
              onClick={() => toggle(d)}
              aria-pressed={selected.includes(d)}
              className={`px-3.5 py-2 rounded-full text-sm font-medium border transition-colors ${
                selected.includes(d)
                  ? "bg-foreground text-background border-foreground"
                  : "bg-card border-input text-foreground hover:border-foreground/40"
              }`}
            >
              {d}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

export default DistrictMultiSelect;
