import { useMemo, useState } from "react";
import { X, Minus, Plus, Sofa, CigaretteOff, Dog, Wifi } from "lucide-react";
import { Button } from "@/components/ui/button";
import { motion, AnimatePresence } from "framer-motion";
import DistrictMultiSelect from "@/components/DistrictMultiSelect";
import { useI18n } from "@/i18n";
import type { TranslationKey } from "@/i18n/translations";
import type { ListingFeature } from "@/lib/api";
import {
  LIFESTYLE_FILTERS,
  PRICE_MAX,
  PRICE_MIN,
  defaultFilters,
  priceHistogram,
  type LifestyleFilter,
  type ListingFilters,
  type ListingTypeFilter,
} from "@/lib/deckFilters";

interface FilterModalProps {
  open: boolean;
  onClose: () => void;
  onApply?: (filters: ListingFilters) => void;
  /**
   * Destedeki ilanların fiyatları (bkz. deckFilters.listingPrice). Fiyat
   * çubuğunun arkasındaki dağılım bunlardan çizilir; yeterli fiyat yoksa
   * dağılım hiç gösterilmez. Eskiden burada uydurma, sabit bir dizi vardı.
   */
  prices?: number[];
}

// Yaşam tarzı çipleri: kimlik deckFilters'ta, etiket sözlükte (filter.<kimlik>).
const lifestyleChips: { value: LifestyleFilter; key: TranslationKey }[] =
  LIFESTYLE_FILTERS.map(value => ({ value, key: `filter.${value}` as TranslationKey }));

// Ev özellikleri: `value` doğrudan backend sütun adıdır, böylece seçim hem
// istemcide hem `GET /api/listings?features=` sorgusunda aynı anlama gelir.
const featureChips: { value: ListingFeature; key: TranslationKey }[] = [
  { value: "furnished", key: "filter.furnished" },
  { value: "elevator", key: "filter.elevator" },
  { value: "parking", key: "filter.parking" },
  { value: "internet_included", key: "filter.internet" },
  { value: "heating_included", key: "filter.heating" },
  { value: "balcony", key: "filter.balcony" },
  { value: "natural_gas", key: "filter.gas" },
];
const listingTypeOptions: { value: ListingTypeFilter; key: TranslationKey }[] = [
  { value: "all", key: "filter.all" },
  { value: "ev_ilani", key: "common.houseListing" },
  { value: "kisisel_ilan", key: "common.personalListing" },
];

// Kısayollar ayrı bir filtre havuzu DEĞİLDİR: aşağıdaki gerçek çiplerin
// (özellik ya da yaşam tarzı) seçimini paylaşırlar, biri değişince diğeri de
// değişir. Yalnızca gerçekten veriye dayanan filtreler burada yer alabilir.
type QuickChip = { icon: typeof Sofa; key: TranslationKey } & (
  | { kind: "feature"; value: ListingFeature }
  | { kind: "lifestyle"; value: LifestyleFilter }
);

const quickFilters: QuickChip[] = [
  { icon: Sofa, kind: "feature", value: "furnished", key: "filter.furnished" },
  { icon: Wifi, kind: "feature", value: "internet_included", key: "filter.internet" },
  { icon: Dog, kind: "lifestyle", value: "petFriendly", key: "filter.petFriendly" },
  { icon: CigaretteOff, kind: "lifestyle", value: "noSmoke", key: "filter.noSmoke" },
];

const FilterModal = ({ open, onClose, onApply, prices = [] }: FilterModalProps) => {
  const { t, n } = useI18n();
  const [listingType, setListingType] = useState<ListingTypeFilter>(defaultFilters.listingType);
  const [priceRange, setPriceRange] = useState<number[]>([...defaultFilters.priceRange]);
  const [rooms, setRooms] = useState(0);
  const [selectedLifestyle, setSelectedLifestyle] = useState<LifestyleFilter[]>([]);
  const [selectedFeatures, setSelectedFeatures] = useState<ListingFeature[]>([]);
  const [districts, setDistricts] = useState<string[]>([]);

  const toggleChip = <T extends string>(arr: T[], setArr: (v: T[]) => void, val: T) => {
    setArr(arr.includes(val) ? arr.filter(v => v !== val) : [...arr, val]);
  };

  // Kısayol çipi, karşılığı olan gerçek çipin state'ini değiştirir.
  const isQuickActive = (q: QuickChip) =>
    q.kind === "feature"
      ? selectedFeatures.includes(q.value)
      : selectedLifestyle.includes(q.value);

  const toggleQuick = (q: QuickChip) => {
    if (q.kind === "feature") toggleChip(selectedFeatures, setSelectedFeatures, q.value);
    else toggleChip(selectedLifestyle, setSelectedLifestyle, q.value);
  };

  const clearAll = () => {
    setListingType(defaultFilters.listingType); setPriceRange([...defaultFilters.priceRange]);
    setRooms(0);
    setSelectedLifestyle([]); setSelectedFeatures([]);
    setDistricts([]);
    onApply?.(defaultFilters);
  };

  const applyFilters = () => {
    onApply?.({
      listingType,
      priceRange: [priceRange[0], priceRange[1]],
      rooms,
      lifestyle: selectedLifestyle,
      features: selectedFeatures,
      districts,
    });
    onClose();
  };

  const histogram = useMemo(() => priceHistogram(prices), [prices]);
  const maxBar = Math.max(1, ...histogram);
  const span = PRICE_MAX - PRICE_MIN;

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.95, opacity: 0 }}
            className="bg-card rounded-2xl border border-border shadow-2xl w-full max-w-[640px] max-h-[85vh] flex flex-col"
            onClick={e => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-border">
              <div />
              <h2 className="font-display text-xl font-semibold text-foreground">{t("filter.title")}</h2>
              <button onClick={onClose} aria-label={t("common.close")} className="w-9 h-9 -mr-2 rounded-full flex items-center justify-center text-foreground hover:bg-muted transition-colors">
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Scrollable content */}
            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-8">

              {/* Recommended */}
              <div>
                <h3 className="text-lg text-foreground mb-3">{t("filter.recommended")}</h3>
                <div className="grid grid-cols-4 gap-3">
                  {quickFilters.map(f => {
                    const active = isQuickActive(f);
                    return (
                      <button
                        key={f.value}
                        onClick={() => toggleQuick(f)}
                        className={`flex flex-col items-center gap-2 p-4 rounded-xl border transition-colors ${
                          active ? "border-foreground bg-muted" : "border-border hover:border-foreground/40"
                        }`}
                      >
                        <f.icon className={`w-6 h-6 ${active ? "text-foreground" : "text-muted-foreground"}`} />
                        <span className="text-[12px] font-semibold text-foreground text-center leading-tight">{t(f.key)}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <hr className="border-border" />

              {/* Listing type */}
              <div>
                <h3 className="text-lg text-foreground mb-3">{t("filter.listingType")}</h3>
                <div className="flex rounded-xl border border-border overflow-hidden">
                  {listingTypeOptions.map(opt => (
                    <button
                      key={opt.value}
                      onClick={() => setListingType(opt.value)}
                      className={`flex-1 py-3 text-sm font-medium transition-colors ${
                        listingType === opt.value
                          ? "bg-primary text-primary-foreground"
                          : "bg-card text-foreground hover:bg-muted"
                      }`}
                    >
                      {t(opt.key)}
                    </button>
                  ))}
                </div>
              </div>

              <hr className="border-border" />

              {/* Semt: tek kampüs çevresine odaklanmak için. Sunucu da
                  ?district= destekliyor; deste istemcide süzülüyor. */}
              <div>
                <h3 className="text-lg text-foreground mb-1">{t("filter.districts")}</h3>
                <p className="text-xs text-muted-foreground mb-3">{t("filter.districtsSub")}</p>
                <DistrictMultiSelect selected={districts} onChange={setDistricts} maxHeightClass="max-h-[180px]" />
              </div>

              <hr className="border-border" />

              {/* Price range */}
              <div>
                <h3 className="text-lg text-foreground mb-1">{t("filter.budget")}</h3>
                <p className="text-xs text-muted-foreground mb-4">{t("filter.budgetSub")}</p>
                {/* Gerçek ilan fiyatlarının dağılımı; az ilanda hiç çizilmez. */}
                {histogram.length > 0 && (
                  <div className="flex items-end gap-[2px] h-16 mb-2" aria-hidden="true">
                    {histogram.map((v, i) => {
                      const pct = (v / maxBar) * 100;
                      const pos = i / histogram.length;
                      const minPos = (priceRange[0] - PRICE_MIN) / span;
                      const maxPos = (priceRange[1] - PRICE_MIN) / span;
                      const inRange = pos >= minPos && pos <= maxPos;
                      return (
                        <div
                          key={i}
                          className={`flex-1 rounded-t-sm transition-colors ${inRange ? "bg-primary" : "bg-muted"}`}
                          // Boş kutu da ince bir çizgi olarak görünsün; aralık okunur kalır.
                          style={{ height: v > 0 ? `${Math.max(pct, 6)}%` : "2px" }}
                        />
                      );
                    })}
                  </div>
                )}
                {/* Dual range - using two native inputs */}
                <div className="relative h-6 mb-4">
                  <input
                    type="range" min={PRICE_MIN} max={PRICE_MAX} step={500}
                    value={priceRange[0]}
                    onChange={e => setPriceRange([Math.min(Number(e.target.value), priceRange[1] - 500), priceRange[1]])}
                    className="absolute inset-0 w-full appearance-none bg-transparent pointer-events-none [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-card [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-foreground [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:cursor-pointer"
                  />
                  <input
                    type="range" min={PRICE_MIN} max={PRICE_MAX} step={500}
                    value={priceRange[1]}
                    onChange={e => setPriceRange([priceRange[0], Math.max(Number(e.target.value), priceRange[0] + 500)])}
                    className="absolute inset-0 w-full appearance-none bg-transparent pointer-events-none [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-card [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-foreground [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:cursor-pointer"
                  />
                </div>
                <div className="flex justify-between">
                  <div className="border border-border rounded-xl px-4 py-2.5">
                    <div className="text-[12px] text-muted-foreground">{t("filter.min")}</div>
                    <div className="text-sm font-semibold text-foreground">{n(priceRange[0])} TL</div>
                  </div>
                  <div className="border border-border rounded-xl px-4 py-2.5 text-right">
                    <div className="text-[12px] text-muted-foreground">{t("filter.max")}</div>
                    <div className="text-sm font-semibold text-foreground">{n(priceRange[1])} TL</div>
                  </div>
                </div>
              </div>

              <hr className="border-border" />

              {/* Rooms — ilanlarda yalnızca oda sayısı var; kişi/banyo verisi
                  toplanmadığı için o sayaçlar kaldırıldı. */}
              <div>
                <h3 className="text-lg text-foreground mb-1">{t("filter.rooms")}</h3>
                <p className="text-xs text-muted-foreground mb-2">{t("filter.roomsSub")}</p>
                <div className="flex items-center justify-between py-3">
                  <span className="text-sm text-foreground">{t("filter.roomsMin")}</span>
                  <div className="flex items-center gap-4">
                    <button
                      onClick={() => setRooms(Math.max(0, rooms - 1))}
                      disabled={rooms === 0}
                      className="w-8 h-8 rounded-full border border-border flex items-center justify-center text-foreground disabled:opacity-30 hover:bg-muted"
                    >
                      <Minus className="w-3.5 h-3.5" />
                    </button>
                    <span className="text-sm font-medium text-foreground w-8 text-center">
                      {rooms === 0 ? t("filter.any") : rooms}
                    </span>
                    <button
                      onClick={() => setRooms(rooms + 1)}
                      className="w-8 h-8 rounded-full border border-border flex items-center justify-center text-foreground hover:bg-muted"
                    >
                      <Plus className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </div>

              <hr className="border-border" />

              {/* Lifestyle */}
              <div>
                <h3 className="text-lg text-foreground mb-1">{t("filter.lifestyle")}</h3>
                {/* Kural deckFilters.matchesLifestyle'da: metin gerçek davranışı anlatıyor. */}
                <p className="text-xs text-muted-foreground mb-3">{t("filter.lifestyleSub")}</p>
                <div className="flex flex-wrap gap-2">
                  {lifestyleChips.map(c => {
                    const active = selectedLifestyle.includes(c.value);
                    return (
                      <button
                        key={c.value}
                        onClick={() => toggleChip(selectedLifestyle, setSelectedLifestyle, c.value)}
                        className={`px-4 py-2 rounded-full text-sm font-medium border transition-colors ${
                          active ? "bg-primary text-primary-foreground border-primary" : "bg-card text-foreground border-border hover:border-foreground/40"
                        }`}
                      >
                        {t(c.key)}
                      </button>
                    );
                  })}
                </div>
              </div>

              <hr className="border-border" />

              {/* Features */}
              <div>
                <h3 className="text-lg text-foreground mb-1">{t("filter.features")}</h3>
                <p className="text-xs text-muted-foreground mb-1">{t("filter.featuresSub")}</p>
                {/* Kapsam notu: bu koşul yalnızca ev ilanlarına uygulanır,
                    kişisel ilanlar (ev arayan kişiler) listede kalır. Hem
                    sunucudaki `features` filtresi hem de istemcideki eşleştirme
                    böyle çalışıyor — metin gerçek davranışı anlatıyor. */}
                <p className="text-xs text-muted-foreground mb-3">{t("filter.featuresScope")}</p>
                <div className="flex flex-wrap gap-2">
                  {featureChips.map(c => {
                    const active = selectedFeatures.includes(c.value);
                    return (
                      <button
                        key={c.value}
                        onClick={() => toggleChip(selectedFeatures, setSelectedFeatures, c.value)}
                        className={`px-4 py-2 rounded-full text-sm font-medium border transition-colors ${
                          active ? "bg-primary text-primary-foreground border-primary" : "bg-card text-foreground border-border hover:border-foreground/40"
                        }`}
                      >
                        {t(c.key)}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Cinsiyet filtresi kaldırıldı: ilanın "ev halkı" bilgisi
                  (kimlerle yaşanacak) henüz toplanmıyor ve sahibinin cinsiyeti
                  destede bilerek gizli. Veri gelince geri gelir (yol haritası
                  1.9). */}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between px-6 py-4 border-t border-border">
              <button onClick={clearAll} className="text-sm font-medium text-foreground underline underline-offset-2">
                {t("filter.clear")}
              </button>
              <Button
                onClick={applyFilters}
                className="rounded-full bg-foreground text-background hover:bg-foreground/90 px-6 h-11 text-sm font-semibold"
              >
                {t("filter.show")}
              </Button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default FilterModal;
