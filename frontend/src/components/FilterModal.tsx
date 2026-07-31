import { useState } from "react";
import { X, Minus, Plus, ShowerHead, Zap, Dog, Wifi } from "lucide-react";
import { Button } from "@/components/ui/button";
import { motion, AnimatePresence } from "framer-motion";
import { useI18n } from "@/i18n";
import type { TranslationKey } from "@/i18n/translations";

export interface ListingFilters {
  listingType: string;
  priceRange: [number, number];
  rooms: number;
  people: number;
  bathrooms: number;
  lifestyle: string[];
  features: string[];
  gender: string;
}

export const defaultFilters: ListingFilters = {
  listingType: "Hepsi",
  priceRange: [1000, 30000],
  rooms: 0,
  people: 0,
  bathrooms: 0,
  lifestyle: [],
  features: [],
  gender: "Hepsi",
};

interface FilterModalProps {
  open: boolean;
  onClose: () => void;
  onApply?: (filters: ListingFilters) => void;
}

const priceDistribution = [3,5,8,12,18,25,30,35,40,38,32,28,24,20,16,14,12,10,8,6,5,4,3,2,2,1,1,1,1,1];

// NOT: `value` alanları filtre kimliğidir ve SwipeScreen'deki eşleştirme
// ile birebir aynı kalmalıdır; yalnızca `key` (ekranda görünen etiket)
// dile göre değişir.
type Chip = { value: string; key: TranslationKey };

const lifestyleChips: Chip[] = [
  { value: "Sigara İçmez", key: "filter.noSmoke" },
  { value: "Hayvan Dostu", key: "filter.petFriendly" },
  { value: "Alkol Kullanmaz", key: "filter.noAlcohol" },
  { value: "Erken Kalkar", key: "filter.earlyBird" },
  { value: "Gece Kuşu", key: "filter.nightOwl" },
  { value: "Temiz ve Düzenli", key: "filter.tidy" },
  { value: "Sosyal", key: "filter.social" },
  { value: "Sessiz", key: "filter.quiet" },
];
const featureChips: Chip[] = [
  { value: "Eşyalı", key: "filter.furnished" },
  { value: "Asansörlü", key: "filter.elevator" },
  { value: "Otoparkı Var", key: "filter.parking" },
  { value: "İnternet Dahil", key: "filter.internet" },
  { value: "Isıtma Dahil", key: "filter.heating" },
  { value: "Balkonlu", key: "filter.balcony" },
  { value: "Doğalgaz", key: "filter.gas" },
];
const genderOptions: Chip[] = [
  { value: "Hepsi", key: "filter.all" },
  { value: "Kadın", key: "filter.female" },
  { value: "Erkek", key: "filter.male" },
];
const listingTypeOptions: Chip[] = [
  { value: "Hepsi", key: "filter.all" },
  { value: "Ev İlanı", key: "common.houseListing" },
  { value: "Kişisel İlan", key: "common.personalListing" },
];

const recommendedFilters: { icon: typeof ShowerHead; value: string; key: TranslationKey }[] = [
  { icon: ShowerHead, value: "Banyo sayısı", key: "filter.bathroomCount" },
  { icon: Zap, value: "Hızlı Eşleşme", key: "filter.fastMatch" },
  { icon: Dog, value: "Hayvan Dostu", key: "filter.petFriendly" },
  { icon: Wifi, value: "İnternet Dahil", key: "filter.internet" },
];

const FilterModal = ({ open, onClose, onApply }: FilterModalProps) => {
  const { t, n } = useI18n();
  const [listingType, setListingType] = useState("Hepsi");
  const [priceRange, setPriceRange] = useState([1000, 30000]);
  const [rooms, setRooms] = useState(0);
  const [people, setPeople] = useState(0);
  const [bathrooms, setBathrooms] = useState(0);
  const [selectedLifestyle, setSelectedLifestyle] = useState<string[]>([]);
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>([]);
  const [gender, setGender] = useState("Hepsi");
  const [selectedRecommended, setSelectedRecommended] = useState<string[]>([]);

  const toggleChip = (arr: string[], setArr: (v: string[]) => void, val: string) => {
    setArr(arr.includes(val) ? arr.filter(v => v !== val) : [...arr, val]);
  };

  const clearAll = () => {
    setListingType("Hepsi"); setPriceRange([1000, 30000]);
    setRooms(0); setPeople(0); setBathrooms(0);
    setSelectedLifestyle([]); setSelectedFeatures([]);
    setGender("Hepsi"); setSelectedRecommended([]);
    onApply?.(defaultFilters);
  };

  const applyFilters = () => {
    onApply?.({
      listingType,
      priceRange: [priceRange[0], priceRange[1]],
      rooms,
      people,
      bathrooms,
      // Önerilen filtrelerden çip karşılığı olanlar aynı havuzda değerlendirilir.
      lifestyle: [...new Set([...selectedLifestyle, ...selectedRecommended])],
      features: selectedFeatures,
      gender,
    });
    onClose();
  };

  const maxBar = Math.max(...priceDistribution);

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
            className="bg-card rounded-2xl shadow-2xl w-full max-w-[640px] max-h-[85vh] flex flex-col"
            onClick={e => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-border">
              <div />
              <h2 className="text-base font-bold text-foreground">{t("filter.title")}</h2>
              <button onClick={onClose} className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-foreground hover:bg-muted/80">
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Scrollable content */}
            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-8">

              {/* Recommended */}
              <div>
                <h3 className="text-sm font-bold text-foreground mb-3">{t("filter.recommended")}</h3>
                <div className="grid grid-cols-4 gap-3">
                  {recommendedFilters.map(f => {
                    const active = selectedRecommended.includes(f.value);
                    return (
                      <button
                        key={f.value}
                        onClick={() => toggleChip(selectedRecommended, setSelectedRecommended, f.value)}
                        className={`flex flex-col items-center gap-2 p-4 rounded-xl border transition-all ${
                          active ? "border-primary bg-primary/5" : "border-border hover:border-primary/30"
                        }`}
                      >
                        <f.icon className={`w-6 h-6 ${active ? "text-primary" : "text-muted-foreground"}`} />
                        <span className="text-[11px] font-medium text-foreground text-center leading-tight">{t(f.key)}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <hr className="border-border" />

              {/* Listing type */}
              <div>
                <h3 className="text-sm font-bold text-foreground mb-3">{t("filter.listingType")}</h3>
                <div className="flex rounded-xl border border-border overflow-hidden">
                  {listingTypeOptions.map(opt => (
                    <button
                      key={opt.value}
                      onClick={() => setListingType(opt.value)}
                      className={`flex-1 py-3 text-sm font-medium transition-all ${
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

              {/* Price range */}
              <div>
                <h3 className="text-sm font-bold text-foreground mb-1">{t("filter.budget")}</h3>
                <p className="text-xs text-muted-foreground mb-4">{t("filter.budgetSub")}</p>
                {/* Histogram */}
                <div className="flex items-end gap-[2px] h-16 mb-2">
                  {priceDistribution.map((v, i) => {
                    const pct = (v / maxBar) * 100;
                    const pos = i / priceDistribution.length;
                    const minPos = (priceRange[0] - 1000) / 29000;
                    const maxPos = (priceRange[1] - 1000) / 29000;
                    const inRange = pos >= minPos && pos <= maxPos;
                    return (
                      <div
                        key={i}
                        className={`flex-1 rounded-t-sm transition-colors ${inRange ? "bg-primary" : "bg-muted"}`}
                        style={{ height: `${pct}%` }}
                      />
                    );
                  })}
                </div>
                {/* Dual range - using two native inputs */}
                <div className="relative h-6 mb-4">
                  <input
                    type="range" min={1000} max={30000} step={500}
                    value={priceRange[0]}
                    onChange={e => setPriceRange([Math.min(Number(e.target.value), priceRange[1] - 500), priceRange[1]])}
                    className="absolute inset-0 w-full appearance-none bg-transparent pointer-events-none [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-card [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-foreground [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:cursor-pointer"
                  />
                  <input
                    type="range" min={1000} max={30000} step={500}
                    value={priceRange[1]}
                    onChange={e => setPriceRange([priceRange[0], Math.max(Number(e.target.value), priceRange[0] + 500)])}
                    className="absolute inset-0 w-full appearance-none bg-transparent pointer-events-none [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-card [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-foreground [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:cursor-pointer"
                  />
                </div>
                <div className="flex justify-between">
                  <div className="border border-border rounded-xl px-4 py-2.5">
                    <div className="text-[10px] text-muted-foreground">{t("filter.min")}</div>
                    <div className="text-sm font-semibold text-foreground">{n(priceRange[0])} ₺</div>
                  </div>
                  <div className="border border-border rounded-xl px-4 py-2.5 text-right">
                    <div className="text-[10px] text-muted-foreground">{t("filter.max")}</div>
                    <div className="text-sm font-semibold text-foreground">{n(priceRange[1])} ₺</div>
                  </div>
                </div>
              </div>

              <hr className="border-border" />

              {/* Rooms and beds */}
              <div>
                <h3 className="text-sm font-bold text-foreground mb-4">{t("filter.roomsSection")}</h3>
                {[
                  { label: t("filter.rooms"), value: rooms, set: setRooms },
                  { label: t("filter.people"), value: people, set: setPeople },
                  { label: t("filter.bathrooms"), value: bathrooms, set: setBathrooms },
                ].map(row => (
                  <div key={row.label} className="flex items-center justify-between py-3 border-b border-border last:border-0">
                    <span className="text-sm text-foreground">{row.label}</span>
                    <div className="flex items-center gap-4">
                      <button
                        onClick={() => row.set(Math.max(0, row.value - 1))}
                        disabled={row.value === 0}
                        className="w-8 h-8 rounded-full border border-border flex items-center justify-center text-foreground disabled:opacity-30 hover:bg-muted"
                      >
                        <Minus className="w-3.5 h-3.5" />
                      </button>
                      <span className="text-sm font-medium text-foreground w-8 text-center">
                        {row.value === 0 ? t("filter.any") : row.value}
                      </span>
                      <button
                        onClick={() => row.set(row.value + 1)}
                        className="w-8 h-8 rounded-full border border-border flex items-center justify-center text-foreground hover:bg-muted"
                      >
                        <Plus className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              <hr className="border-border" />

              {/* Lifestyle */}
              <div>
                <h3 className="text-sm font-bold text-foreground mb-3">{t("filter.lifestyle")}</h3>
                <div className="flex flex-wrap gap-2">
                  {lifestyleChips.map(c => {
                    const active = selectedLifestyle.includes(c.value);
                    return (
                      <button
                        key={c.value}
                        onClick={() => toggleChip(selectedLifestyle, setSelectedLifestyle, c.value)}
                        className={`px-4 py-2 rounded-full text-sm font-medium border transition-all ${
                          active ? "bg-primary text-primary-foreground border-primary" : "bg-card text-foreground border-border hover:border-primary/30"
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
                <h3 className="text-sm font-bold text-foreground mb-3">{t("filter.features")}</h3>
                <div className="flex flex-wrap gap-2">
                  {featureChips.map(c => {
                    const active = selectedFeatures.includes(c.value);
                    return (
                      <button
                        key={c.value}
                        onClick={() => toggleChip(selectedFeatures, setSelectedFeatures, c.value)}
                        className={`px-4 py-2 rounded-full text-sm font-medium border transition-all ${
                          active ? "bg-primary text-primary-foreground border-primary" : "bg-card text-foreground border-border hover:border-primary/30"
                        }`}
                      >
                        {t(c.key)}
                      </button>
                    );
                  })}
                </div>
              </div>

              <hr className="border-border" />

              {/* Gender */}
              <div>
                <h3 className="text-sm font-bold text-foreground mb-3">{t("filter.gender")}</h3>
                <div className="flex gap-2">
                  {genderOptions.map(g => (
                    <button
                      key={g.value}
                      onClick={() => setGender(g.value)}
                      className={`px-5 py-2 rounded-full text-sm font-medium border transition-all ${
                        gender === g.value ? "bg-primary text-primary-foreground border-primary" : "bg-card text-foreground border-border hover:border-primary/30"
                      }`}
                    >
                      {t(g.key)}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between px-6 py-4 border-t border-border">
              <button onClick={clearAll} className="text-sm font-medium text-foreground underline underline-offset-2">
                {t("filter.clear")}
              </button>
              <Button
                onClick={applyFilters}
                className="rounded-full bg-foreground text-background hover:bg-foreground/90 px-6 h-11 text-sm font-bold"
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
