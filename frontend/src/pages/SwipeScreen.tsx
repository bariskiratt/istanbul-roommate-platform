import { useState, useCallback, useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchListings, type ApiListing } from "@/lib/api";
import { motion, useMotionValue, useTransform, AnimatePresence, PanInfo } from "framer-motion";
import { SlidersHorizontal, X, Heart, Zap, MapPin, DollarSign, GraduationCap, ChevronDown, Home, User as UserIcon } from "lucide-react";
import { mockListings, type Listing, type UserProfile } from "@/data/mockData";
import LifestyleTag from "@/components/LifestyleTag";
import BottomNav from "@/components/layout/BottomNav";
import AppHeader from "@/components/layout/AppHeader";
import { Button } from "@/components/ui/button";
import AuthGate from "@/components/AuthGate";
import FilterModal, { type ListingFilters } from "@/components/FilterModal";
import { useAuth } from "@/contexts/AuthContext";

const matchesFilters = (l: Listing, f: ListingFilters): boolean => {
  if (f.listingType === "Ev İlanı" && l.type !== "ev_ilani") return false;
  if (f.listingType === "Kişisel İlan" && l.type !== "kisisel_ilan") return false;

  // Ev ilanında kira, kişisel ilanda bütçe aralığı kesişimi
  const [min, max] = f.priceRange;
  if (l.type === "ev_ilani") {
    if (l.rent !== undefined && (l.rent < min || l.rent > max)) return false;
  } else if (l.budgetMin !== undefined && l.budgetMax !== undefined) {
    if (l.budgetMax < min || l.budgetMin > max) return false;
  }

  if (f.rooms > 0 && (!l.roomCount || parseInt(l.roomCount) < f.rooms)) return false;

  if (f.gender === "Kadın" && l.user.gender !== "kadın") return false;
  if (f.gender === "Erkek" && l.user.gender !== "erkek") return false;

  for (const chip of f.lifestyle) {
    if (chip === "Sigara İçmez" && (l.type === "ev_ilani" ? l.smokingAllowed !== false : l.user.smoking)) return false;
    if (chip === "Hayvan Dostu" && (l.type === "ev_ilani" ? !l.petsAllowed : !l.user.pets)) return false;
    if (chip === "Alkol Kullanmaz" && l.user.alcohol) return false;
    if (chip === "Erken Kalkar" && l.user.sleepSchedule !== "erken") return false;
    if (chip === "Gece Kuşu" && l.user.sleepSchedule !== "gece") return false;
  }

  return true;
};

// API ilanlarının henüz sahibi yok (auth sonraki dilim); kart altındaki
// profil şeridi için nötr bir yer tutucu kullanılır.
const anonUser: UserProfile = {
  id: "anon",
  name: "İlan Sahibi",
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
  weeklySupermatchUsed: false,
  supermatchRemaining: 0,
};

const toDeckListing = (a: ApiListing): Listing => ({
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
  photos: a.photos.length > 0 ? a.photos : anonUser.photos,
  isActive: a.is_active,
  createdAt: a.created_at,
  user: anonUser,
});

const SwipeScreen = () => {
  const { isLoggedIn } = useAuth();
  const [cards, setCards] = useState<Listing[]>([...mockListings].reverse());
  const [expandedCard, setExpandedCard] = useState<string | null>(null);
  const [superMatchLeft, setSuperMatchLeft] = useState(1);
  const [swipeDirection, setSwipeDirection] = useState<"left" | "right" | null>(null);
  const [filterOpen, setFilterOpen] = useState(false);

  const { data: apiListings } = useQuery({
    queryKey: ["listings"],
    queryFn: () => fetchListings(),
    staleTime: 60_000,
  });

  // Gerçek ilanlar destenin en üstüne; mock profiller demoyu dolu tutmak için arkada.
  const allListings = useMemo(
    () => [...(apiListings ?? []).map(toDeckListing), ...mockListings],
    [apiListings],
  );

  useEffect(() => {
    setCards([...allListings].reverse());
  }, [allListings]);

  const applyFilters = (f: ListingFilters) => {
    setCards(allListings.filter(l => matchesFilters(l, f)).reverse());
  };

  const handleSwipe = useCallback((direction: "left" | "right") => {
    setSwipeDirection(direction);
    setTimeout(() => {
      setCards(prev => prev.slice(0, -1));
      setSwipeDirection(null);
    }, 300);
  }, [isLoggedIn]);

  const handleSuperMatch = () => {
    if (superMatchLeft > 0) {
      setSuperMatchLeft(s => s - 1);
      handleSwipe("right");
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
          <button
            onClick={() => setFilterOpen(true)}
            className="w-10 h-10 rounded-2xl bg-card flex items-center justify-center text-foreground hover:bg-muted transition-colors"
            style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}
          >
            <SlidersHorizontal className="w-5 h-5" />
          </button>
        }
      />

      <div className="flex-1 relative flex items-center justify-center px-6 pt-2">
        {cards.length === 0 ? (
          <div className="text-center space-y-4 animate-fade-in">
            <div className="w-24 h-24 rounded-3xl bg-lavender/50 flex items-center justify-center mx-auto">
              <Home className="w-12 h-12 text-primary" />
            </div>
            <h2 className="text-2xl font-bold text-foreground">Şimdilik bu kadar!</h2>
            <p className="text-muted-foreground text-sm max-w-[240px] mx-auto">Yeni ilanlar geldiğinde bildirim alacaksın.</p>
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
          <button
            onClick={handleSuperMatch}
            disabled={superMatchLeft === 0}
            className="btn-supermatch w-[52px] h-[52px] flex items-center justify-center relative animate-pulse-glow disabled:opacity-40 disabled:animate-none"
          >
            <Zap className="w-6 h-6" />
            <span className="absolute -top-1.5 -right-1.5 w-5 h-5 bg-secondary text-primary-foreground text-[10px] font-bold rounded-full flex items-center justify-center">
              {superMatchLeft}
            </span>
          </button>
          <button onClick={() => handleSwipe("right")} className="btn-swipe-like w-[60px] h-[60px] flex items-center justify-center">
            <Heart className="w-7 h-7" />
          </button>
        </div>
      )}

      <AuthGate show={!isLoggedIn} onClose={() => {}} />
      <FilterModal open={filterOpen} onClose={() => setFilterOpen(false)} onApply={applyFilters} />
      <BottomNav />
    </div>
  );
};

/* Card content — photo-dominant with overlay */
const SwipeCard = ({ listing, isTop = true }: { listing: Listing; isTop?: boolean }) => {
  const isHouse = listing.type === "ev_ilani";

  return (
    <div className="card-listing h-full flex flex-col">
      <div className="relative flex-[0_0_65%] overflow-hidden">
        <img src={listing.photos[0]} alt={listing.title} className="w-full h-full object-cover" />
        <div className="absolute top-4 left-4">
          <span className={`px-3 py-1.5 rounded-full text-xs font-semibold backdrop-blur-sm ${
            isHouse ? "bg-lavender/80 text-foreground" : "bg-accent/80 text-accent-foreground"
          }`}>
            {isHouse ? "🏠 Ev İlanı" : "👤 Kişisel İlan"}
          </span>
        </div>
        <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/70 via-black/30 to-transparent p-5 pt-16">
          <h3 className="font-bold text-xl text-white leading-tight">{listing.title}</h3>
          <div className="flex items-center gap-3 mt-2">
            <span className="flex items-center gap-1 text-white/90 text-sm"><MapPin className="w-4 h-4" />{listing.district}</span>
            <span className="font-bold text-white text-lg">
              {isHouse ? `${listing.rent?.toLocaleString("tr-TR")} ₺` : `${listing.budgetMin?.toLocaleString("tr-TR")}–${listing.budgetMax?.toLocaleString("tr-TR")} ₺`}
            </span>
          </div>
          <div className="flex items-center gap-1.5 mt-1.5 text-white/80 text-xs">
            <GraduationCap className="w-3.5 h-3.5" />{listing.user.university}
          </div>
        </div>
      </div>
      <div className="p-5 flex-1 space-y-3">
        <p className="text-sm text-muted-foreground line-clamp-2 leading-relaxed">{listing.description}</p>
        <div className="flex flex-wrap gap-1.5">
          {isHouse && listing.smokingAllowed !== undefined && <LifestyleTag type="smoking" value={listing.smokingAllowed} />}
          {isHouse && listing.petsAllowed !== undefined && <LifestyleTag type="pets" value={listing.petsAllowed} />}
          {!isHouse && (
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
}

const SwipeCardDraggable = ({ listing, onSwipe, expanded, onToggleExpand, direction }: SwipeCardDraggableProps) => {
  const x = useMotionValue(0);
  const rotate = useTransform(x, [-200, 200], [-12, 12]);
  const likeOpacity = useTransform(x, [0, 100], [0, 1]);
  const nopeOpacity = useTransform(x, [-100, 0], [1, 0]);

  const handleDragEnd = (_: any, info: PanInfo) => {
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
        BEĞENDİM ✓
      </motion.div>
      <motion.div className="absolute top-8 left-6 z-10 bg-destructive/90 backdrop-blur-sm text-destructive-foreground px-5 py-2.5 rounded-2xl font-bold text-xl rotate-[15deg]" style={{ opacity: nopeOpacity }}>
        GEÇ ✗
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
              <div className="flex flex-wrap gap-2">
                <LifestyleTag type="smoking" value={listing.user.smoking} />
                <LifestyleTag type="pets" value={listing.user.pets} />
                <LifestyleTag type="alcohol" value={listing.user.alcohol} />
                <LifestyleTag type="sleep" value={listing.user.sleepSchedule} />
              </div>
              <div className="card-listing p-4 flex items-center gap-3">
                <img src={listing.user.photos[0]} alt="" className="w-14 h-14 rounded-full object-cover" />
                <div>
                  <p className="font-semibold text-foreground">{listing.user.name}</p>
                  <p className="text-xs text-muted-foreground">{listing.user.university} • {listing.user.department}</p>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

export default SwipeScreen;
