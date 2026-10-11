import { useState, useCallback, useEffect, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
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
import { SlidersHorizontal, RotateCcw, X, Heart, MapPin, GraduationCap, ChevronDown, Home, Flag } from "lucide-react";
import LifestyleTag from "@/components/LifestyleTag";
import UserAvatar from "@/components/UserAvatar";
import BottomNav from "@/components/layout/BottomNav";
import AppHeader from "@/components/layout/AppHeader";
import { Button } from "@/components/ui/button";
import AuthGate from "@/components/AuthGate";
import FilterModal, { defaultFilters, type ListingFilters } from "@/components/FilterModal";
import FairPriceBadge from "@/components/FairPriceBadge";
import ReportDialog from "@/components/ReportDialog";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/i18n";
import { BRAND } from "@/lib/brand";

// Kartın altındaki profil şeridi: ilan sahibi.
interface UserProfile {
  id: string;
  name: string;
  gender: "erkek" | "kadın" | "belirtmek_istemiyorum";
  birthYear: number;
  university: string;
  department: string;
  year: number;
  budgetMin: number;
  budgetMax: number;
  smoking: boolean;
  pets: boolean;
  alcohol: boolean;
  sleepSchedule: "erken" | "gece" | "esnek";
  preferredDistrict: string;
  bio: string;
  photos: string[];
}

// Destedeki kart. Sunucudaki ilan (ApiListing) toDeckListing ile buna çevrilir.
interface Listing {
  id: string;
  userId: string;
  type: "ev_ilani" | "kisisel_ilan";
  title: string;
  description: string;
  rent?: number;
  budgetMin?: number;
  budgetMax?: number;
  district: string;
  roomCount?: string;
  smokingAllowed?: boolean;
  petsAllowed?: boolean;
  photos: string[];
  isActive: boolean;
  createdAt: string;
  user: UserProfile;
}

// Deste kartı: kart tipine ek olarak gerçek ilanın ev özelliklerini taşır.
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

// API ilanı sahibinin yalnızca adını ve üniversitesini taşır; kart altındaki
// profil şeridinin geri kalanı için nötr bir yer tutucu kullanılır. Fotoğrafı
// yok: şeritte sahibin adının baş harfleri görünür (UserAvatar).
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
  photos: [],
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
  photos: a.photos,
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
  const navigate = useNavigate();
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
    // Karar sunucuya yalnızca girişliyken ve sunucudaki bir ilan için yazılır.
    const card = cards[cards.length - 1];
    if (card && isLoggedIn && card.id.startsWith("api-")) {
      const listingId = Number(card.id.slice(4));
      postSwipe(listingId, direction === "right" ? "like" : "pass")
        .then(res => {
          // Deste sorgusu YENİDEN ÇEKİLMEZ (çekilirse elde kalan kartlar
          // sıfırlanır), ama önbellekteki kayıt da öylece bırakılamaz:
          // başka sekmeye geçip dönünce bileşen yeniden kurulur ve desteyi
          // bu önbellekten inşa eder — kaydırılan kartlar geri gelirdi.
          // Bu yüzden karar verilen ilan önbellekten tek tek düşürülür.
          queryClient.setQueriesData<ApiListing[]>(
            { queryKey: ["listings", "deck"] },
            old => old?.filter(l => l.id !== listingId),
          );
          queryClient.invalidateQueries({ queryKey: ["matches"] });
          queryClient.invalidateQueries({ queryKey: ["received-likes"] });
          if (res.matched) {
            toast.success(t("swipe.matched"), { description: t("swipe.matchedDesc") });
          }
        })
        // Sunucu kaydırmayı reddedebilir: ilan sahibi askıya alındıysa ya da
        // ilan yayından kalktıysa 404 döner. Sessizce yutmak kullanıcıya
        // kararı kaydedilmiş gibi gösteriyordu; artık sebebini görüyor.
        .catch(err => {
          toast.error(err instanceof Error ? err.message : t("swipe.failed"));
        });
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

  return (
    <div className="min-h-screen bg-background flex flex-col pb-20">
      <AppHeader
        title={BRAND}
        rightAction={
          <div className="flex items-center gap-1">
            {/* Deste sıfırlama — yalnızca yönetici (sunucu ucu da öyle) */}
            {isAdmin && (
              <button
                onClick={handleResetDeck}
                disabled={resetting}
                title={t("swipe.resetDeck")}
                aria-label={t("swipe.resetDeck")}
                className="w-10 h-10 rounded-full border border-border flex items-center justify-center text-foreground hover:bg-muted transition-colors disabled:opacity-40"
              >
                <RotateCcw className={`w-[18px] h-[18px] ${resetting ? "animate-spin" : ""}`} />
              </button>
            )}
            <button
              onClick={() => setFilterOpen(true)}
              title={t("filter.title")}
              aria-label={t("filter.title")}
              className={`relative w-10 h-10 rounded-full border flex items-center justify-center transition-colors ${
                activeFilters ? "border-foreground bg-foreground text-background" : "border-border text-foreground hover:bg-muted"
              }`}
            >
              <SlidersHorizontal className="w-[18px] h-[18px]" />
            </button>
          </div>
        }
      />

      <div className="flex-1 relative flex items-center justify-center px-4 pt-3">
        {isPending ? (
          <div className="w-full max-w-sm animate-pulse" style={{ height: '68vh' }}>
            <div className="h-full rounded-2xl bg-muted" />
          </div>
        ) : cards.length === 0 ? (
          <div className="w-full max-w-sm px-2 text-left space-y-4 animate-fade-in">
            <h2 className="text-[2rem] leading-tight text-foreground">{t("swipe.emptyTitle")}</h2>
            <p className="text-muted-foreground leading-relaxed">
              {t(activeFilters ? "swipe.emptyFiltered" : "swipe.emptyAll")}
            </p>
            {activeFilters ? (
              <Button variant="outline" onClick={() => setActiveFilters(null)}>
                {t("swipe.clearFilters")}
              </Button>
            ) : (
              // Yayının ilk günlerinde deste çoğu zaman boş olacak; öğrenci
              // burada takılı kalmasın, ilan vermeye ya da haritaya geçsin.
              <div className="flex flex-wrap items-center gap-2 pt-2">
                <Button onClick={() => navigate(isLoggedIn ? "/create-listing" : "/onboarding")}>
                  {t("swipe.emptyCreate")}
                </Button>
                <Button variant="outline" onClick={() => navigate("/explore")}>
                  {t("swipe.emptyMap")}
                </Button>
              </div>
            )}
          </div>
        ) : (
          <div className="relative w-full max-w-sm" style={{ height: '68vh' }}>
            {nextCard && (
              <div className="absolute inset-0 translate-y-2 scale-[0.96] rounded-2xl overflow-hidden" aria-hidden="true">
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
        <div className="flex items-center justify-center gap-6 py-4">
          <button onClick={() => handleSwipe("left")} aria-label={t("likes.pass")} className="btn-swipe-pass w-16 h-16 flex items-center justify-center">
            <X className="w-7 h-7" strokeWidth={2.4} />
          </button>
          <button onClick={() => handleSwipe("right")} aria-label={t("swipe.likeLabel")} className="btn-swipe-like w-16 h-16 flex items-center justify-center">
            <Heart className="w-7 h-7" strokeWidth={2.2} />
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

/*
 * Kart: Hinge gibi fotoğraf üstte ve çerçeveli, metin altta kâğıdın üstünde.
 * Fotoğrafın üstüne yazı basılmaz; başlık ve fiyat her fotoğrafta okunur.
 * İlan sahibinin kendi yazdığı açıklama çizgili kâğıtta durur.
 */
const SwipeCard = ({ listing, isTop = true }: { listing: Listing; isTop?: boolean }) => {
  const isHouse = listing.type === "ev_ilani";
  const { t, n } = useI18n();
  const apiId = listing.id.startsWith("api-") ? Number(listing.id.slice(4)) : null;

  return (
    <div className="card-listing h-full flex flex-col">
      <div className="relative flex-[0_0_50%] m-2 mb-0 rounded-xl overflow-hidden bg-muted">
        {listing.photos[0] ? (
          <img src={listing.photos[0]} alt={isTop ? listing.title : ""} className="w-full h-full object-cover" draggable={false} />
        ) : (
          // Sunucu ilan başına en az 3 fotoğraf ister; bu yalnızca bir güvence.
          <div className="w-full h-full flex items-center justify-center">
            <Home className="w-12 h-12 text-muted-foreground/50" />
          </div>
        )}
        <span className="absolute top-3 left-3 px-3 py-1 rounded-full text-[12px] font-semibold bg-card/95 text-foreground">
          {isHouse ? t("common.houseListing") : t("common.personalListing")}
        </span>
      </div>

      <div className="px-4 pt-3 pb-4 flex-1 min-h-0 flex flex-col gap-2.5">
        <div>
          <h3 className="font-display text-[1.45rem] leading-tight text-foreground line-clamp-1">{listing.title}</h3>
          <p className="mt-0.5 text-sm text-muted-foreground flex items-center gap-1">
            <MapPin className="w-3.5 h-3.5" />
            {listing.district}
            {listing.roomCount && <span className="ml-1.5">{listing.roomCount}</span>}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <p className="text-[15px]">
            <span className="marker font-semibold text-[17px]">
              {isHouse
                ? `${n(listing.rent ?? 0)} ₺`
                : `${n(listing.budgetMin ?? 0)}–${n(listing.budgetMax ?? 0)} ₺`}
            </span>
            {isHouse && <span className="text-muted-foreground text-[13px] ml-0.5">{t("common.roomShare")}</span>}
          </p>
          {/* Gerçek ilanlarda modelin adil fiyat kıyası */}
          {isHouse && apiId !== null && isTop && <FairPriceBadge listingId={apiId} />}
        </div>

        <p className="paper-ruled rounded-lg text-[14px] text-foreground flex-1 min-h-[3.5rem] overflow-hidden">
          {listing.description}
        </p>

        <div className="flex items-center gap-2.5">
          <UserAvatar name={listing.user.name} photo={listing.user.photos[0]} className="w-7 h-7 text-[11px]" />
          <p className="text-[13px] text-muted-foreground truncate">
            <span className="font-semibold text-foreground">{listing.user.name}</span>
            {listing.user.university && <>, {listing.user.university}</>}
          </p>
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
  // Yalnızca sunucudaki ilanların id'si vardır ("api-<id>").
  const apiListingId = listing.id.startsWith("api-") ? Number(listing.id.slice(4)) : null;
  const x = useMotionValue(0);
  const rotate = useTransform(x, [-200, 200], [-10, 10]);
  const likeOpacity = useTransform(x, [0, 100], [0, 1]);
  const nopeOpacity = useTransform(x, [-100, 0], [1, 0]);

  const handleDragEnd = (_: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
    if (info.offset.x > 100) onSwipe("right");
    else if (info.offset.x < -100) onSwipe("left");
  };

  const exitX = direction === "right" ? 500 : direction === "left" ? -500 : 0;
  const exitRotate = direction === "right" ? 18 : direction === "left" ? -18 : 0;

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
      {/* Sürüklerken basılan lastik mühürler */}
      <motion.div className="absolute top-10 left-6 z-10 -rotate-[14deg] pointer-events-none" style={{ opacity: likeOpacity }}>
        <span className="stamp text-2xl px-4 py-1.5 bg-card/80">{t("swipe.like")}</span>
      </motion.div>
      <motion.div className="absolute top-10 right-6 z-10 rotate-[14deg] pointer-events-none" style={{ opacity: nopeOpacity }}>
        <span className="stamp stamp-red text-2xl px-4 py-1.5 bg-card/80">{t("swipe.pass")}</span>
      </motion.div>

      <div className="h-full" onClick={onToggleExpand}>
        <SwipeCard listing={listing} />
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ y: "100%" }} animate={{ y: "22%" }} exit={{ y: "100%" }}
            transition={{ type: "spring", damping: 28, stiffness: 300 }}
            className="absolute inset-0 bg-card rounded-2xl border border-border overflow-y-auto z-20"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex justify-center pt-3 pb-3"><div className="w-10 h-1 rounded-full bg-border" /></div>
            <div className="px-5 pb-[30%] space-y-5">
              <div className="flex items-start justify-between gap-3">
                <h3 className="font-display text-2xl leading-tight text-foreground">{listing.title}</h3>
                <button onClick={onToggleExpand} aria-label={t("common.close")} className="w-9 h-9 shrink-0 rounded-full border border-border flex items-center justify-center hover:bg-muted">
                  <ChevronDown className="w-5 h-5 text-foreground" />
                </button>
              </div>
              <p className="paper-ruled rounded-lg text-[15px] text-foreground whitespace-pre-line">{listing.description}</p>
              {listing.type === "ev_ilani" && apiListingId !== null && (
                <FairPriceBadge listingId={apiListingId} detailed />
              )}
              {listing.user.id !== "anon" && (
                <div className="flex flex-wrap gap-2">
                  <LifestyleTag type="smoking" value={listing.user.smoking} />
                  <LifestyleTag type="pets" value={listing.user.pets} />
                  <LifestyleTag type="alcohol" value={listing.user.alcohol} />
                  <LifestyleTag type="sleep" value={listing.user.sleepSchedule} />
                </div>
              )}
              <div className="flex items-center gap-3 rounded-xl border border-border p-3">
                <UserAvatar name={listing.user.name} photo={listing.user.photos[0]} className="w-12 h-12 text-base" />
                <div className="min-w-0">
                  <p className="font-display text-lg leading-tight text-foreground truncate">{listing.user.name}</p>
                  {listing.user.university && (
                    <p className="text-[13px] text-muted-foreground flex items-center gap-1 truncate">
                      <GraduationCap className="w-3.5 h-3.5 shrink-0" />{listing.user.university}
                    </p>
                  )}
                </div>
              </div>
              {/* Bildirme girişli kullanıcıya açıktır (sunucu 401 döner) */}
              {isLoggedIn && apiListingId !== null && (
                <button
                  onClick={() => onReport(apiListingId, listing.title)}
                  className="flex items-center gap-2 text-[13px] font-medium text-muted-foreground hover:text-destructive transition-colors"
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
