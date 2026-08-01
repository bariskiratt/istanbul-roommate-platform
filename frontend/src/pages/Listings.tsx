import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Zap, MapPin, Home, MessageCircle, X, ChevronLeft, ChevronRight, SlidersHorizontal, BedDouble, DollarSign, RefreshCw } from "lucide-react";
import BottomNav from "@/components/layout/BottomNav";
import AppHeader from "@/components/layout/AppHeader";
import { Button } from "@/components/ui/button";
import { motion, AnimatePresence } from "framer-motion";
import FilterModal, { type ListingFilters, defaultFilters } from "@/components/FilterModal";
import { fetchListings, postSwipe, LISTING_FEATURES, type ApiListing, type ListingFeature } from "@/lib/api";
import FairPriceBadge from "@/components/FairPriceBadge";
import { useAuth } from "@/contexts/AuthContext";
import { toast } from "sonner";
import { useI18n } from "@/i18n";
import type { TranslationKey } from "@/i18n/translations";

// Çip değerleri filtre kimliğidir (ilçe adı / oda sayısı doğrudan veriyle
// karşılaştırılır); yalnızca "Tümü" çevrilir.
const ALL_FILTER = "Tümü";
const filters = [ALL_FILTER, "Kadıköy", "Beşiktaş", "Üsküdar", "Şişli", "1+1", "2+1", "3+1"];

// Ev özelliği -> etiket anahtarı (FilterModal'daki çiplerle aynı anahtarlar).
const featureLabels: Record<ListingFeature, TranslationKey> = {
  furnished: "filter.furnished",
  elevator: "filter.elevator",
  parking: "filter.parking",
  internet_included: "filter.internet",
  heating_included: "filter.heating",
  balcony: "filter.balcony",
  natural_gas: "filter.gas",
};

/** İlanda açıkça true olan özellikler; null ("bilinmiyor") gösterilmez. */
const listingFeatures = (l: ApiListing): ListingFeature[] =>
  LISTING_FEATURES.filter(key => l[key] === true);

const priceLabel = (l: ApiListing, n: (v: number) => string) =>
  l.type === "ev_ilani"
    ? `${n(l.rent ?? 0)} ₺`
    : `${n(l.budget_min ?? 0)}–${n(l.budget_max ?? 0)} ₺`;

const listingTags = (l: ApiListing): TranslationKey[] => {
  const tags: TranslationKey[] = [];
  if (l.smoking_allowed === false) tags.push("tag.noSmoke");
  if (l.pets_allowed) tags.push("tag.pets");
  return tags;
};

const matchesModalFilters = (l: ApiListing, f: ListingFilters): boolean => {
  if (f.listingType === "Ev İlanı" && l.type !== "ev_ilani") return false;
  if (f.listingType === "Kişisel İlan" && l.type !== "kisisel_ilan") return false;

  const [min, max] = f.priceRange;
  // Varsayılan aralık (1000-30000) "filtre yok" demektir; dokunulmadıysa
  // aralık dışı ilanlar elenmez. null alanlar da elenmez (backend null döner).
  const rangeTouched = min !== defaultFilters.priceRange[0] || max !== defaultFilters.priceRange[1];
  if (rangeTouched) {
    if (l.type === "ev_ilani") {
      if (l.rent != null && (l.rent < min || l.rent > max)) return false;
    } else if (l.budget_min != null && l.budget_max != null) {
      if (l.budget_max < min || l.budget_min > max) return false;
    }
  }

  if (f.rooms > 0 && (!l.room_count || parseInt(l.room_count) < f.rooms)) return false;
  if (f.lifestyle.includes("Sigara İçmez") && l.smoking_allowed !== false) return false;
  if (f.lifestyle.includes("Hayvan Dostu") && !l.pets_allowed) return false;
  // Ev özellikleri: sunucudaki `features` filtresiyle aynı kural — yalnızca
  // açıkça true olan alanlar geçer, bilinmeyen (null) eşleşmez. Koşul yalnızca
  // ev ilanlarına uygulanır; kişisel ilanlarda bu alanlar hiç olamayacağı için
  // filtre onları elemez (FilterModal'daki kapsam notu bunu söylüyor).
  if (l.type === "ev_ilani") {
    for (const key of f.features) {
      if (l[key] !== true) return false;
    }
  }

  return true;
};

const Listings = () => {
  const navigate = useNavigate();
  const { user: viewer } = useAuth();
  const { t, n } = useI18n();
  const [activeFilter, setActiveFilter] = useState(ALL_FILTER);
  const [selectedListing, setSelectedListing] = useState<ApiListing | null>(null);
  const [filterOpen, setFilterOpen] = useState(false);
  const [modalFilters, setModalFilters] = useState<ListingFilters>(defaultFilters);

  const isAdmin = viewer?.is_admin === true;

  const { data: listings, isLoading, isError, refetch } = useQuery({
    queryKey: ["listings"],
    queryFn: () => fetchListings(),
  });

  const filtered = (listings ?? []).filter(l => {
    if (!matchesModalFilters(l, modalFilters)) return false;
    if (activeFilter === ALL_FILTER) return true;
    return l.district === activeFilter || l.room_count === activeFilter;
  });

  // Bu sayfa şimdilik yalnızca yöneticiye açık
  if (!isAdmin) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center px-6 text-center gap-4 pb-24">
        <h1 className="text-2xl font-semibold text-foreground">{t("listings.closedTitle")}</h1>
        <p className="text-sm text-muted-foreground max-w-sm">{t("listings.closedDesc")}</p>
        <Button onClick={() => navigate("/swipe")} className="rounded-full px-6">
          {t("listings.goDiscover")}
        </Button>
        <BottomNav />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex flex-col pb-24">
      <AppHeader
        title={t("nav.houses")}
        rightAction={
          <button onClick={() => setFilterOpen(true)} className="w-10 h-10 rounded-2xl bg-card flex items-center justify-center text-foreground hover:bg-muted transition-colors" style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
            <SlidersHorizontal className="w-5 h-5" />
          </button>
        }
      />

      <div className="px-6 pt-4 pb-2">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-bold text-foreground">{t("listings.heading")}</h1>
          <span className="px-2.5 py-1 rounded-full text-[10px] font-semibold bg-primary/10 text-primary flex items-center gap-1">
            <Zap className="w-3 h-3" /> {t("listings.live")}
          </span>
        </div>
        <p className="text-sm text-muted-foreground mt-1">{t("listings.sub")}</p>
      </div>

      {/* Filter row */}
      <div className="px-6 py-3">
        <div className="flex gap-2 overflow-x-auto scrollbar-hide">
          {filters.map(f => (
            <button
              key={f}
              onClick={() => setActiveFilter(f)}
              className={`px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-all ${
                activeFilter === f
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "bg-card border border-border text-foreground hover:border-primary/30"
              }`}
            >
              {f === ALL_FILTER ? t("listings.filterAll") : f}
            </button>
          ))}
        </div>
      </div>

      {/* Listings — 2 col grid desktop, 1 col mobile */}
      <div className="px-6 flex-1">
        {isLoading ? (
          <div className="text-center py-16 text-sm text-muted-foreground">{t("listings.loading")}</div>
        ) : isError ? (
          <div className="text-center py-16 space-y-3">
            <p className="font-semibold text-foreground">{t("listings.loadFailed")}</p>
            <p className="text-sm text-muted-foreground">{t("listings.backendHint")}</p>
            <Button variant="outline" size="sm" onClick={() => refetch()} className="rounded-full">
              <RefreshCw className="w-3.5 h-3.5 mr-2" /> {t("common.retry")}
            </Button>
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16 space-y-3">
            <div className="w-20 h-20 rounded-3xl bg-muted flex items-center justify-center mx-auto">
              <Home className="w-10 h-10 text-muted-foreground" />
            </div>
            <p className="font-semibold text-foreground">{t("listings.emptyTitle")}</p>
            <p className="text-sm text-muted-foreground">{t("listings.emptyDesc")}</p>
            <Button size="sm" onClick={() => navigate("/create-listing")} className="rounded-full">
              {t("create.title")}
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filtered.map(listing => (
              <div
                key={listing.id}
                onClick={() => setSelectedListing(listing)}
                className="card-listing overflow-hidden cursor-pointer hover:shadow-lg transition-shadow"
                style={{ maxHeight: 320 }}
              >
                <div className="h-[180px] overflow-hidden rounded-t-xl bg-muted">
                  {listing.photos[0] ? (
                    <img
                      src={listing.photos[0]}
                      alt={listing.title}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <Home className="w-10 h-10 text-muted-foreground" />
                    </div>
                  )}
                </div>
                <div className="p-4 space-y-2">
                  <h3 className="font-bold text-[15px] text-foreground truncate">{listing.title}</h3>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1"><MapPin className="w-3 h-3" /> {listing.district}</span>
                    {listing.room_count && (
                      <>
                        <span>·</span>
                        <span className="flex items-center gap-1"><Home className="w-3 h-3" /> {listing.room_count}</span>
                      </>
                    )}
                    <span>·</span>
                    <span className="font-bold text-accent">{priceLabel(listing, n)}</span>
                  </div>
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex flex-wrap gap-1.5">
                      {listingTags(listing).slice(0, 2).map(key => (
                        <span key={key} className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-muted text-muted-foreground">
                          {t(key)}
                        </span>
                      ))}
                      {/* Kartta yer sınırlı: en fazla 2 özellik, kalanı detayda */}
                      {listingFeatures(listing).slice(0, 2).map(key => (
                        <span key={key} className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-lavender/50 text-foreground">
                          {t(featureLabels[key])}
                        </span>
                      ))}
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-primary/10 text-primary">
                        {listing.type === "ev_ilani" ? t("profile.house") : t("profile.personal")}
                      </span>
                    </div>
                    <button
                      onClick={e => { e.stopPropagation(); setSelectedListing(listing); }}
                      className="text-xs text-primary font-medium hover:underline whitespace-nowrap"
                    >
                      {t("listings.details")}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Listing Detail Modal */}
      <ListingDetailModal listing={selectedListing} onClose={() => setSelectedListing(null)} />

      {/* Filter Modal */}
      <FilterModal open={filterOpen} onClose={() => setFilterOpen(false)} onApply={setModalFilters} />

      <BottomNav />
    </div>
  );
};

/* ─── Detail Modal ─── */
const ListingDetailModal = ({ listing, onClose }: { listing: ApiListing | null; onClose: () => void }) => {
  const navigate = useNavigate();
  const { isLoggedIn, user: me } = useAuth();
  const { t, n } = useI18n();
  const [photoIndex, setPhotoIndex] = useState(0);

  if (!listing) return null;

  const isOwn = me !== null && listing.owner_id === me.id;

  // Girişliyse beğeni gönderir (eşleşme akışına girer); değilse girişe yönlendirir
  const handleContact = async () => {
    if (!isLoggedIn) {
      navigate("/login");
      return;
    }
    try {
      const res = await postSwipe(listing.id, "like");
      if (res.matched) {
        toast.success(t("swipe.matched"), { description: t("listings.matchedDesc") });
        navigate("/messages");
      } else {
        toast.success(t("listings.likeSent"), { description: t("listings.likeSentDesc") });
        onClose();
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("listings.likeFailed"));
    }
  };

  const isHouse = listing.type === "ev_ilani";
  const features = listingFeatures(listing);

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-end sm:items-center justify-center"
        onClick={onClose}
      >
        <motion.div
          initial={{ y: 100, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 100, opacity: 0 }}
          className="bg-card rounded-t-3xl sm:rounded-2xl w-full sm:max-w-lg max-h-[90vh] overflow-y-auto"
          onClick={e => e.stopPropagation()}
        >
          {/* Close */}
          <div className="sticky top-0 z-10 flex justify-between items-center p-4">
            <div />
            <button onClick={onClose} aria-label={t("common.close")} className="w-8 h-8 rounded-full bg-muted/80 backdrop-blur-sm flex items-center justify-center">
              <X className="w-4 h-4 text-foreground" />
            </button>
          </div>

          {/* Photo gallery */}
          {listing.photos.length > 0 && (
            <div className="px-4 -mt-4">
              <div className="relative h-[260px] rounded-xl overflow-hidden">
                <img
                  src={listing.photos[photoIndex]}
                  alt={listing.title}
                  className="w-full h-full object-cover"
                />
                {listing.photos.length > 1 && (
                  <>
                    <button
                      onClick={() => setPhotoIndex(i => Math.max(0, i - 1))}
                      className="absolute left-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-card/80 backdrop-blur-sm flex items-center justify-center"
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => setPhotoIndex(i => Math.min(listing.photos.length - 1, i + 1))}
                      className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-card/80 backdrop-blur-sm flex items-center justify-center"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                    <div className="absolute bottom-2 left-1/2 -translate-x-1/2 flex gap-1.5">
                      {listing.photos.map((_, i) => (
                        <div key={i} className={`w-2 h-2 rounded-full ${i === photoIndex ? "bg-white" : "bg-white/50"}`} />
                      ))}
                    </div>
                  </>
                )}
              </div>
              {/* Thumbnails */}
              <div className="flex gap-2 mt-2 overflow-x-auto">
                {listing.photos.map((p, i) => (
                  <button
                    key={i}
                    onClick={() => setPhotoIndex(i)}
                    className={`w-16 h-12 rounded-lg overflow-hidden flex-shrink-0 border-2 transition-all ${i === photoIndex ? "border-primary" : "border-transparent opacity-60"}`}
                  >
                    <img src={p} alt="" className="w-full h-full object-cover" />
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Info */}
          <div className="p-5 space-y-4">
            <div>
              <h2 className="text-xl font-bold text-foreground">{listing.title}</h2>
              <div className="flex items-center gap-3 mt-1 text-sm text-muted-foreground">
                <span className="flex items-center gap-1"><MapPin className="w-3.5 h-3.5" /> {listing.district}</span>
                {listing.room_count && (
                  <>
                    <span>·</span>
                    <span className="flex items-center gap-1"><BedDouble className="w-3.5 h-3.5" /> {listing.room_count}</span>
                  </>
                )}
                <span>·</span>
                <span className="font-bold text-accent text-base">
                  {priceLabel(listing, n)}{isHouse ? t("common.perMonth") : ""}
                </span>
              </div>
            </div>

            {/* Adil fiyat analizi (ev arkadaşlığı bazlı oda payı) */}
            {isHouse && <FairPriceBadge listingId={listing.id} detailed />}

            <hr className="border-border" />

            {/* Description */}
            <div>
              <h3 className="text-sm font-bold text-foreground mb-2">{t("listings.description")}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-line">{listing.description}</p>
            </div>

            {!isHouse && (
              <div className="flex items-center gap-2">
                <DollarSign className="w-3.5 h-3.5 text-accent" />
                <span className="text-xs font-semibold text-foreground">
                  {t("listings.budget")}: {priceLabel(listing, n)}
                </span>
              </div>
            )}

            {/* Ev özellikleri — yalnızca ilan sahibinin işaretledikleri */}
            {isHouse && features.length > 0 && (
              <>
                <hr className="border-border" />
                <div>
                  <h4 className="text-xs font-semibold text-foreground mb-2">{t("listings.features")}</h4>
                  <div className="flex flex-wrap gap-2">
                    {features.map(key => (
                      <span key={key} className="px-3 py-1 rounded-full text-[11px] font-medium bg-lavender/50 text-foreground">
                        {t(featureLabels[key])}
                      </span>
                    ))}
                  </div>
                </div>
              </>
            )}

            {/* Kurallar (ev ilanı) */}
            {isHouse && (
              <>
                <hr className="border-border" />
                <div>
                  <h4 className="text-xs font-semibold text-foreground mb-2">{t("listings.rules")}</h4>
                  <div className="flex flex-wrap gap-2">
                    <span className={`px-3 py-1 rounded-full text-[11px] font-medium ${listing.smoking_allowed ? "bg-accent/15 text-foreground" : "bg-muted text-muted-foreground"}`}>
                      {listing.smoking_allowed ? t("listings.smokingAllowed") : t("listings.smokingBanned")}
                    </span>
                    <span className={`px-3 py-1 rounded-full text-[11px] font-medium ${listing.pets_allowed ? "bg-accent/15 text-foreground" : "bg-muted text-muted-foreground"}`}>
                      {listing.pets_allowed ? t("listings.petsAllowed") : t("listings.petsBanned")}
                    </span>
                  </div>
                </div>
              </>
            )}

            {/* CTA */}
            {!isOwn && (
              <Button
                onClick={handleContact}
                className="w-full h-12 rounded-full bg-gradient-to-r from-primary to-secondary text-primary-foreground font-bold text-sm"
              >
                <MessageCircle className="w-4 h-4 mr-2" /> {isLoggedIn ? t("listings.contact") : t("listings.contactLogin")}
              </Button>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

export default Listings;
