import { useState, useCallback, useEffect, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  fetchListings,
  postSwipe,
  resetMyDeck,
  LISTING_FEATURES,
  type ApiListing,
  type ListingFeature,
} from "@/lib/api";
import { motion, useMotionValue, useTransform, AnimatePresence, PanInfo } from "framer-motion";
import { SlidersHorizontal, RotateCcw, X, Heart, MapPin, DollarSign, GraduationCap, ChevronDown, Home, User as UserIcon, Flag } from "lucide-react";
import { type Listing, type UserProfile } from "@/data/mockData";
import LifestyleTag from "@/components/LifestyleTag";
import BottomNav from "@/components/layout/BottomNav";
import AppHeader from "@/components/layout/AppHeader";
import { Button } from "@/components/ui/button";
import AuthGate from "@/components/AuthGate";
import FilterModal, { defaultFilters, type ListingFilters } from "@/components/FilterModal";
import FairPriceBadge from "@/components/FairPriceBadge";
import ReportDialog from "@/components/ReportDialog";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/i18n";

// Deste kartı: mock tipine ek olarak gerçek ilanın ev özelliklerini taşır.
type DeckListing = Listing & {
  features?: Partial<Record<ListingFeature, boolean>>;
};

const matchesFilters = (l: DeckListing, f: ListingFilters): boolean => {
  if (f.listingType === "Ev İlanı" && l.type !== "ev_ilani") return false;
  if (f.listingType === "Kişisel İlan" && l.type !== "kisisel_ilan") return false;

  // Ev ilanında kira, kişisel ilanda bütçe aralığı kesişimi.
  // Varsayılan aralığa (1000-30000) dokunulmadıysa "filtre yok" demektir;
  // aksi halde aralık dışındaki ilanlar kullanıcı istemeden elenirdi.
  const [min, max] = f.priceRange;
  const rangeTouched =
    min !== defaultFilters.priceRange[0] || max !== defaultFilters.priceRange[1];
  if (rangeTouched) {
    if (l.type === "ev_ilani") {
      if (l.rent != null && (l.rent < min || l.rent > max)) return false;
    } else if (l.budgetMin != null && l.budgetMax != null) {
      if (l.budgetMax < min || l.budgetMin > max) return false;
    }
  }

  if (f.rooms > 0 && (!l.roomCount || parseInt(l.roomCount) < f.rooms)) return false;

  // Ev özellikleri: yalnızca ilanda açıkça "var" diyen alanlar geçer;
  // bilinmeyen (null) alan eşleşme sayılmaz — sunucudaki `features`
  // filtresiyle aynı kural. Koşul yalnızca ev ilanlarına uygulanır: kişisel
  // ilanda (ev arayan kişi) asansör/otopark gibi alanlar hiç olamayacağı için
  // filtre onları elemek yerine kapsam dışı bırakır — sunucu da böyle yapıyor.
  if (l.type === "ev_ilani") {
    for (const key of f.features) {
      if (l.features?.[key] !== true) return false;
    }
  }

  // API ilanlarında kullanıcı profili yer tutucu ("anon"); bilinmeyen alan
  // üzerinden eleme yapılmaz, yoksa cinsiyet filtresi tüm desteyi boşaltır.
  const profileKnown = l.user.id !== "anon";
  if (profileKnown) {
    if (f.gender === "Kadın" && l.user.gender !== "kadın") return false;
    if (f.gender === "Erkek" && l.user.gender !== "erkek") return false;
  }

  for (const chip of f.lifestyle) {
    if (chip === "Sigara İçmez" && (l.type === "ev_ilani" ? l.smokingAllowed !== false : profileKnown && l.user.smoking)) return false;
    if (chip === "Hayvan Dostu" && (l.type === "ev_ilani" ? !l.petsAllowed : profileKnown && !l.user.pets)) return false;
    if (!profileKnown) continue;
    if (chip === "Alkol Kullanmaz" && l.user.alcohol) return false;
    if (chip === "Erken Kalkar" && l.user.sleepSchedule !== "erken") return false;
    if (chip === "Gece Kuşu" && l.user.sleepSchedule !== "gece") return false;
  }

  return true;
};

/** Seçim varsayılanla aynı mı (yani gerçekte hiçbir filtre yok mu)? */
const isDefaultFilters = (f: ListingFilters): boolean =>
  f.listingType === defaultFilters.listingType &&
  f.priceRange[0] === defaultFilters.priceRange[0] &&
  f.priceRange[1] === defaultFilters.priceRange[1] &&
  f.rooms === defaultFilters.rooms &&
  f.gender === defaultFilters.gender &&
  f.lifestyle.length === 0 &&
  f.features.length === 0;

// API ilanlarının henüz sahibi yok (auth sonraki dilim); kart altındaki
// profil şeridi için nötr bir yer tutucu kullanılır.
const anonUser: UserProfile = {
  id: "anon",
  name: "",
  gender: "belirtmek_istemiyorum",
  birthYear: 2000,
  university: "",
  department: "",
  year: 0,
  budgetMin: 0,
  budgetMax: 0,
  smoking: false,
  pets: false,
  alcohol: false,
  sleepSchedule: "esnek",
  preferredDistrict: "",
  bio: "",
  photos: ["https://api.dicebear.com/9.x/thumbs/svg?seed=roommatch"],
};

const toDeckListing = (a: ApiListing, ownerFallback: string): DeckListing => ({
  id: `api-${a.id}`,
  userId: "anon",
  type: a.type,
  title: a.title,
  description: a.description,
  rent: a.rent ?? undefined,
  budgetMin: a.budget_min ?? undefined,
  budgetMax: a.budget_max ?? undefined,
  district: a.district,
  roomCount: a.room_count ?? undefined,
  smokingAllowed: a.smoking_allowed ?? undefined,
  petsAllowed: a.pets_allowed ?? undefined,
  // Sunucu belirtilmemiş özellikler için null döner; yalnızca true "var"dır.
  features: Object.fromEntries(
    LISTING_FEATURES.map(key => [key, a[key] === true]),
  ) as Partial<Record<ListingFeature, boolean>>,
  photos: a.photos.length > 0 ? a.photos : anonUser.photos,
  isActive: a.is_active,
  createdAt: a.created_at,
  user: {
    ...anonUser,
    name: a.owner_name ?? ownerFallback,
    university: a.owner_university ?? "",
  },
});

const SwipeScreen = () => {
  const { isLoggedIn, user: me } = useAuth();
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [cards, setCards] = useState<DeckListing[]>([]);
  const [expandedCard, setExpandedCard] = useState<string | null>(null);
  const [swipeDirection, setSwipeDirection] = useState<"left" | "right" | null>(null);
  const [filterOpen, setFilterOpen] = useState(false);
  const [resetting, setResetting] = useState(false);
  // Deste sıfırlama ucu sunucuda yalnızca yöneticiye açık; düğmeyi de öyle
  // gösteriyoruz ki kimse kesin 403 alacak bir işlem görmesin.
  const isAdmin = me?.is_admin === true;

  // Rapor kutusu kartın DIŞINDA durur: kart sürüklenirken transform aldığı
  // için içine konan `position: fixed` panel karta göre konumlanır ve ekranı
  // kaplayamaz. Hedef, kutu kapandıktan sonra da tutulur (çıkış animasyonu).
  const [reportTarget, setReportTarget] = useState<{ id: number; title: string } | null>(null);
  const [reportOpen, setReportOpen] = useState(false);
  const openReport = (id: number, title: string) => {
    setReportTarget({ id, title });
    setReportOpen(true);
  };

  // Filtre state'te tutulur; liste yenilense de seçim kaybolmaz
  const [activeFilters, setActiveFilters] = useState<ListingFilters | null>(null);

  // Ev özellikleri sunucuda da elenir; seçim değişince sorgu anahtarı
  // değiştiği için react-query desteyi yeniden çeker.
  const selectedFeatures = activeFilters?.features ?? [];
  const featureKey = selectedFeatures.join(",");

  // Deste: karar verilmemiş ilanlar (girişliyse kaydırdıkları ve kendi
  // ilanları sunucuda elenir; girişsizken tüm ilanlar gösterilir)
  const { data: apiListings, isPending } = useQuery({
    queryKey: ["listings", "deck", isLoggedIn, featureKey],
    queryFn: () =>
      fetchListings({
        unswiped: isLoggedIn,
        features: featureKey ? (featureKey.split(",") as ListingFeature[]) : undefined,
      }),
    staleTime: 60_000,
  });

  // Deste yalnızca gerçek ilanlardan oluşur (kendi ilanların hariç).
  // NOT: Deste boşaldığında örnek/mock ilana DÜŞÜLMEZ — mock kartların
  // kararları sunucuya yazılamadığından her yenilemede geri gelir ve
  // kullanıcı aynı kartları sonsuza dek kaydırır.
  const ownerFallback = t("swipe.owner");
  const allListings = useMemo(
    () =>
      (apiListings ?? [])
        .filter(a => !me || a.owner_id !== me.id)
        .map(a => toDeckListing(a, ownerFallback)),
    [apiListings, me, ownerFallback],
  );

  useEffect(() => {
    const base = activeFilters
      ? allListings.filter(l => matchesFilters(l, activeFilters))
      : allListings;
    setCards([...base].reverse());
  }, [allListings, activeFilters]);

  // Hiçbir şey seçilmemişse (ör. modaldaki "Temizle") filtre yok sayılır;
  // boş deste metni ve "filtreleri temizle" düğmesi böylece doğru çıkar.
  const applyFilters = (f: ListingFilters) =>
    setActiveFilters(isDefaultFilters(f) ? null : f);

  const handleSwipe = useCallback((direction: "left" | "right") => {
    // Gerçek (API'den gelen) ilanlarda karar sunucuya yazılır; mock kartlar
    // yalnızca demo malzemesi olduğundan atlanır.
    const card = cards[cards.length - 1];
    if (card && isLoggedIn && card.id.startsWith("api-")) {
      postSwipe(Number(card.id.slice(4)), direction === "right" ? "like" : "pass")
        .then(res => {
          // Deste sorgusu tazelenmesin: kart zaten elden çıktı, yeniden
          // çekilirse liste sıfırlanır. Yalnızca eşleşme ekranları tazelenir.
          queryClient.invalidateQueries({ queryKey: ["matches"] });
          queryClient.invalidateQueries({ queryKey: ["received-likes"] });
          if (res.matched) {
            toast.success(t("swipe.matched"), { description: t("swipe.matchedDesc") });
          }
        })
        .catch(() => {}); // kart zaten kaydı; sessizce geç
    }
    setSwipeDirection(direction);
    setTimeout(() => {
      setCards(prev => prev.slice(0, -1));
      setSwipeDirection(null);
    }, 300);
  }, [isLoggedIn, cards, queryClient, t]);

  // Kaydırma geçmişini siler: sunucudaki kararlar gidince deste baştan gelir.
  // Eşleşmeler ve sohbetler silinmez (sunucu yalnızca Swipe satırlarını siler),
  // bu yüzden onay metninde de böyle yazıyor.
  const handleResetDeck = async () => {
    if (!window.confirm(t("swipe.resetConfirm"))) return;
    setResetting(true);
    try {
      const { deleted } = await resetMyDeck();
      // Deste sorgusu yeniden çekilmeli; "unswiped" sonucu tamamen değişti.
      await queryClient.invalidateQueries({ queryKey: ["listings"] });
      toast.success(t("swipe.resetDone", { count: deleted }));
    } catch (err) {
      // Sunucunun açıklaması (ör. 403 "yönetici yetkisi gerekiyor") olduğu gibi.
      toast.error(err instanceof Error ? err.message : t("swipe.resetFailed"));
    } finally {
      setResetting(false);
    }
  };

  const currentCard = cards[cards.length - 1];
  const nextCard = cards[cards.length - 2];
  const thirdCard = cards[cards.length - 3];

  return (
    <div className="min-h-screen bg-background flex flex-col pb-20">
      <AppHeader
        title="RoomMatch"
        rightAction={
          <div className="flex items-center gap-2">
            {/* Deste sıfırlama — yalnızca yönetici (sunucu ucu da öyle) */}
            {isAdmin && (
              <button
                onClick={handleResetDeck}
                disabled={resetting}
                title={t("swipe.resetDeck")}
                aria-label={t("swipe.resetDeck")}
                className="w-10 h-10 rounded-2xl bg-card flex items-center justify-center text-foreground hover:bg-muted transition-colors disabled:opacity-40"
                style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}
              >
                <RotateCcw className={`w-5 h-5 ${resetting ? "animate-spin" : ""}`} />
              </button>
            )}
            <button
              onClick={() => setFilterOpen(true)}
              title={t("filter.title")}
              aria-label={t("filter.title")}
              className="w-10 h-10 rounded-2xl bg-card flex items-center justify-center text-foreground hover:bg-muted transition-colors"
              style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}
            >
              <SlidersHorizontal className="w-5 h-5" />
            </button>
          </div>
        }
      />

      <div className="flex-1 relative flex items-center justify-center px-6 pt-2">
        {isPending ? (
          <div className="w-full max-w-sm animate-pulse" style={{ height: '70vh' }}>
            <div className="h-full rounded-2xl bg-muted" />
          </div>
        ) : cards.length === 0 ? (
          <div className="text-center space-y-4 animate-fade-in">
            <div className="w-24 h-24 rounded-3xl bg-lavender/50 flex items-center justify-center mx-auto">
              <Home className="w-12 h-12 text-primary" />
            </div>
            <h2 className="text-2xl font-bold text-foreground">{t("swipe.emptyTitle")}</h2>
            <p className="text-muted-foreground text-sm max-w-[260px] mx-auto">
              {t(activeFilters ? "swipe.emptyFiltered" : "swipe.emptyAll")}
            </p>
            {activeFilters && (
              <Button variant="outline" onClick={() => setActiveFilters(null)}>
                {t("swipe.clearFilters")}
              </Button>
            )}
          </div>
        ) : (
          <div className="relative w-full max-w-sm" style={{ height: '70vh' }}>
            {thirdCard && (
              <div className="absolute inset-x-3 top-5 bottom-0 scale-[0.90] opacity-40 rounded-2xl overflow-hidden">
                <div className="card-listing h-full bg-card" />
              </div>
            )}
            {nextCard && (
              <div className="absolute inset-x-1.5 top-2.5 bottom-0 scale-[0.95] opacity-60 rounded-2xl overflow-hidden">
                <SwipeCard listing={nextCard} isTop={false} />
              </div>
            )}
            <AnimatePresence>
              {currentCard && (
                <SwipeCardDraggable
                  key={currentCard.id}
                  listing={currentCard}
                  onSwipe={handleSwipe}
                  expanded={expandedCard === currentCard.id}
                  onToggleExpand={() => setExpandedCard(e => e === currentCard.id ? null : currentCard.id)}
                  direction={swipeDirection}
                  onReport={openReport}
                />
              )}
            </AnimatePresence>
          </div>
        )}
      </div>

      {cards.length > 0 && (
        <div className="flex items-center justify-center gap-8 py-4">
          <button onClick={() => handleSwipe("left")} className="btn-swipe-pass w-[60px] h-[60px] flex items-center justify-center">
            <X className="w-7 h-7" />
          </button>
          <button onClick={() => handleSwipe("right")} className="btn-swipe-like w-[60px] h-[60px] flex items-center justify-center">
            <Heart className="w-7 h-7" />
          </button>
        </div>
      )}

      <AuthGate show={!isLoggedIn} onClose={() => {}} />
      <FilterModal open={filterOpen} onClose={() => setFilterOpen(false)} onApply={applyFilters} />
      {reportTarget && (
        <ReportDialog
          open={reportOpen}
          onClose={() => setReportOpen(false)}
          targetType="listing"
          targetId={reportTarget.id}
          targetLabel={reportTarget.title}
        />
      )}
      <BottomNav />
    </div>
  );
};

/* Card content — photo-dominant with overlay */
const SwipeCard = ({ listing, isTop = true }: { listing: Listing; isTop?: boolean }) => {
  const isHouse = listing.type === "ev_ilani";
  const { t, n } = useI18n();

  return (
    <div className="card-listing h-full flex flex-col">
      <div className="relative flex-[0_0_65%] overflow-hidden">
        <img src={listing.photos[0]} alt={listing.title} className="w-full h-full object-cover" />
        <div className="absolute top-4 left-4">
          <span className={`px-3 py-1.5 rounded-full text-xs font-semibold backdrop-blur-sm ${
            isHouse ? "bg-lavender/80 text-foreground" : "bg-accent/80 text-accent-foreground"
          }`}>
            {isHouse ? `🏠 ${t("common.houseListing")}` : `👤 ${t("common.personalListing")}`}
          </span>
        </div>
        <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/70 via-black/30 to-transparent p-5 pt-16">
          <h3 className="font-bold text-xl text-white leading-tight">{listing.title}</h3>
          <div className="flex items-center gap-3 mt-2">
            <span className="flex items-center gap-1 text-white/90 text-sm"><MapPin className="w-4 h-4" />{listing.district}</span>
            <span className="font-bold text-white text-lg">
              {isHouse
                ? `${n(listing.rent ?? 0)} ₺`
                : `${n(listing.budgetMin ?? 0)}–${n(listing.budgetMax ?? 0)} ₺`}
            </span>
            {isHouse && <span className="text-white/70 text-xs">{t("common.roomShare")}</span>}
          </div>
          {/* Gerçek ilanlarda modelin adil fiyat kıyası */}
          {isHouse && listing.id.startsWith("api-") && (
            <div className="mt-2">
              <FairPriceBadge listingId={Number(listing.id.slice(4))} onPhoto />
            </div>
          )}
          {listing.user.university && (
            <div className="flex items-center gap-1.5 mt-1.5 text-white/80 text-xs">
              <GraduationCap className="w-3.5 h-3.5" />{listing.user.university}
            </div>
          )}
        </div>
      </div>
      <div className="p-5 flex-1 space-y-3">
        <p className="text-sm text-muted-foreground line-clamp-2 leading-relaxed">{listing.description}</p>
        <div className="flex flex-wrap gap-1.5">
          {isHouse && listing.smokingAllowed !== undefined && <LifestyleTag type="smoking" value={listing.smokingAllowed} />}
          {isHouse && listing.petsAllowed !== undefined && <LifestyleTag type="pets" value={listing.petsAllowed} />}
          {/* Profil bilinmiyorsa ("anon") uydurma yaşam tarzı etiketi basılmaz */}
          {!isHouse && listing.user.id !== "anon" && (
            <>
              <LifestyleTag type="smoking" value={listing.user.smoking} />
              <LifestyleTag type="sleep" value={listing.user.sleepSchedule} />
            </>
          )}
        </div>
        <div className="flex items-center gap-3 pt-1">
          <img src={listing.user.photos[0]} alt="" className="w-8 h-8 rounded-full object-cover" />
          <span className="text-xs text-muted-foreground font-medium">{listing.user.name}</span>
        </div>
      </div>
    </div>
  );
};

interface SwipeCardDraggableProps {
  listing: Listing;
  onSwipe: (dir: "left" | "right") => void;
  expanded: boolean;
  onToggleExpand: () => void;
  direction: "left" | "right" | null;
  /** Genişletilmiş karttaki "bu ilanı bildir" bağlantısı. */
  onReport: (listingId: number, title: string) => void;
}

const SwipeCardDraggable = ({ listing, onSwipe, expanded, onToggleExpand, direction, onReport }: SwipeCardDraggableProps) => {
  const { t } = useI18n();
  const { isLoggedIn } = useAuth();
  // Yalnızca sunucudaki ilanların id'si vardır; mock kart raporlanamaz.
  const apiListingId = listing.id.startsWith("api-") ? Number(listing.id.slice(4)) : null;
  const x = useMotionValue(0);
  const rotate = useTransform(x, [-200, 200], [-12, 12]);
  const likeOpacity = useTransform(x, [0, 100], [0, 1]);
  const nopeOpacity = useTransform(x, [-100, 0], [1, 0]);

  const handleDragEnd = (_: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
    if (info.offset.x > 100) onSwipe("right");
    else if (info.offset.x < -100) onSwipe("left");
  };

  const exitX = direction === "right" ? 500 : direction === "left" ? -500 : 0;
  const exitRotate = direction === "right" ? 20 : direction === "left" ? -20 : 0;

  return (
    <motion.div
      className="absolute inset-0 cursor-grab active:cursor-grabbing swipe-card"
      style={{ x, rotate }}
      drag="x"
      dragConstraints={{ left: 0, right: 0 }}
      dragElastic={0.7}
      onDragEnd={handleDragEnd}
      animate={direction ? { x: exitX, rotate: exitRotate, opacity: 0 } : {}}
      transition={{ duration: 0.3 }}
    >
      <motion.div className="absolute top-8 right-6 z-10 bg-accent/90 backdrop-blur-sm text-accent-foreground px-5 py-2.5 rounded-2xl font-bold text-xl rotate-[-15deg]" style={{ opacity: likeOpacity }}>
        {t("swipe.like")}
      </motion.div>
      <motion.div className="absolute top-8 left-6 z-10 bg-destructive/90 backdrop-blur-sm text-destructive-foreground px-5 py-2.5 rounded-2xl font-bold text-xl rotate-[15deg]" style={{ opacity: nopeOpacity }}>
        {t("swipe.pass")}
      </motion.div>

      <div className="h-full" onClick={onToggleExpand}>
        <SwipeCard listing={listing} />
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ y: "100%" }} animate={{ y: "40%" }} exit={{ y: "100%" }}
            transition={{ type: "spring", damping: 25, stiffness: 300 }}
            className="absolute inset-0 bg-card rounded-t-3xl overflow-y-auto z-20"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex justify-center pt-3 pb-4"><div className="w-10 h-1 rounded-full bg-muted" /></div>
            <div className="px-6 pb-8 space-y-5">
              <div className="flex items-center justify-between">
                <h3 className="font-bold text-xl text-foreground">{listing.title}</h3>
                <button onClick={onToggleExpand} className="w-8 h-8 rounded-full bg-muted flex items-center justify-center">
                  <ChevronDown className="w-5 h-5 text-foreground" />
                </button>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">{listing.description}</p>
              {listing.type === "ev_ilani" && listing.id.startsWith("api-") && (
                <FairPriceBadge listingId={Number(listing.id.slice(4))} detailed />
              )}
              {listing.user.id !== "anon" && (
                <div className="flex flex-wrap gap-2">
                  <LifestyleTag type="smoking" value={listing.user.smoking} />
                  <LifestyleTag type="pets" value={listing.user.pets} />
                  <LifestyleTag type="alcohol" value={listing.user.alcohol} />
                  <LifestyleTag type="sleep" value={listing.user.sleepSchedule} />
                </div>
              )}
              <div className="card-listing p-4 flex items-center gap-3">
                <img src={listing.user.photos[0]} alt="" className="w-14 h-14 rounded-full object-cover" />
                <div>
                  <p className="font-semibold text-foreground">{listing.user.name}</p>
                  <p className="text-xs text-muted-foreground">{listing.user.university} • {listing.user.department}</p>
                </div>
              </div>
              {/* Bildirme girişli kullanıcıya açıktır (sunucu 401 döner) */}
              {isLoggedIn && apiListingId !== null && (
                <button
                  onClick={() => onReport(apiListingId, listing.title)}
                  className="flex items-center gap-2 text-xs font-medium text-muted-foreground hover:text-destructive transition-colors"
                >
                  <Flag className="w-3.5 h-3.5" />
                  {t("report.reportListing")}
                </button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

export default SwipeScreen;
