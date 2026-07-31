import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, Check, ChevronDown } from "lucide-react";
import { fetchDepartments } from "@/lib/api";
import { useI18n } from "@/i18n";

interface Props {
  value: string;
  onChange: (department: string) => void;
}

/**
 * Bölüm seçici: liste backend'den gelir (tek kaynak) ve serbest metin
 * girilemez — kullanıcı yalnızca listeden seçer.
 */
const DepartmentPicker = ({ value, onChange }: Props) => {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const { data: groups = {}, isLoading, isError, refetch } = useQuery({
    queryKey: ["departments"],
    queryFn: fetchDepartments,
    staleTime: 24 * 60 * 60 * 1000,
    retry: 2,
  });

  const filtered = useMemo(() => {
    const q = query.trim().toLocaleLowerCase("tr");
    if (!q) return groups;
    const out: Record<string, string[]> = {};
    for (const [group, items] of Object.entries(groups)) {
      const hits = items.filter(d => d.toLocaleLowerCase("tr").includes(q));
      if (hits.length) out[group] = hits;
    }
    return out;
  }, [groups, query]);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full h-14 px-4 rounded-2xl bg-card border border-border text-left flex items-center justify-between hover:border-primary/40 transition-colors"
      >
        <span className={value ? "text-foreground" : "text-muted-foreground"}>
          {value || t(isLoading ? "dept.loading" : "dept.select")}
        </span>
        <ChevronDown className={`w-4 h-4 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute z-50 mt-2 w-full rounded-2xl bg-card border border-border shadow-xl overflow-hidden">
          <div className="relative border-b border-border">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              autoFocus
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder={t("dept.search")}
              className="w-full h-12 pl-9 pr-3 bg-transparent text-sm outline-none text-foreground placeholder:text-muted-foreground"
            />
          </div>

          <div className="max-h-64 overflow-y-auto py-1">
            {isLoading && (
              <p className="px-4 py-6 text-sm text-muted-foreground text-center">
                {t("dept.loading")}
              </p>
            )}
            {(isError || (!isLoading && Object.keys(groups).length === 0)) && (
              <div className="px-4 py-6 text-center space-y-2">
                <p className="text-sm text-muted-foreground">
                  {t("dept.loadFailed")}
                </p>
                <button
                  type="button"
                  onClick={() => refetch()}
                  className="text-sm font-semibold text-primary hover:underline"
                >
                  {t("common.retry")}
                </button>
              </div>
            )}
            {!isLoading && Object.keys(groups).length > 0 && Object.keys(filtered).length === 0 && (
              <p className="px-4 py-6 text-sm text-muted-foreground text-center">
                {t("dept.noMatch")}
              </p>
            )}
            {Object.entries(filtered).map(([group, items]) => (
              <div key={group}>
                <p className="px-4 pt-3 pb-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                  {group}
                </p>
                {items.map(d => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => {
                      onChange(d);
                      setOpen(false);
                      setQuery("");
                    }}
                    className={`w-full text-left px-4 py-2.5 text-sm flex items-center justify-between hover:bg-muted transition-colors ${
                      value === d ? "text-primary font-semibold" : "text-foreground"
                    }`}
                  >
                    {d}
                    {value === d && <Check className="w-4 h-4" />}
                  </button>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default DepartmentPicker;
