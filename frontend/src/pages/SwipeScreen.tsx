import { useState, useCallback, useEffect, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  fetchListings,
  postSwipe,
  resetMyDeck,
  type ApiListing,
  type LikeTarget,
  type ListingFeature,
  type SwipeResult,
} from "@/lib/api";
import { motion, useMotionValue, useTransform, AnimatePresence, PanInfo } from "framer-motion";
import { SlidersHorizontal, RotateCcw, X, Heart, MapPin, Home, Flag } from "lucide-react";
import UserAvatar from "@/components/UserAvatar";
import StudentCard from "@/components/campus/StudentCard";
import ProfileTimeline, { LikeHeart } from "@/components/campus/ProfileTimeline";
import LikeComposer, { type LikePreview } from "@/components/LikeComposer";
import { interleave, isLikablePrompt, listingPrompts, type TimelineItem } from "@/lib/prompts";
import BottomNav from "@/components/layout/BottomNav";
import AppHeader from "@/components/layout/AppHeader";
import { Button } from "@/components/ui/button";
import AuthGate from "@/components/AuthGate";
import FilterModal from "@/components/FilterModal";
import { isDefaultFilters, listingPrice, matchesFilters, type ListingFilters } from "@/lib/deckFilters";
import FairPriceBadge from "@/components/FairPriceBadge";
import ReportDialog from "@/components/ReportDialog";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/i18n";
import { BRAND } from "@/lib/brand";

// Deste kartı: sunucudaki ilanın (ApiListing) kart için düzleştirilmiş hâli.
// Filtreler bu düz alanlara değil `source`a bakar (bkz. lib/deckFilters.ts).
interface DeckListing {
  id: string;
  type: ApiListing["type"];
  title: string;
  description: string;
  rent?: number;
  budgetMin?: number;
  budgetMax?: number;
  district: string;
  roomCount?: string;
  photos: string[];
  /** Kartta görünen ad (girişsizken sunucu adı göndermez, yer tutucu). */
  ownerName: string;
  source: ApiListing;
}

/** Kalbe basılan şey: sunucuya giden hedef ve paneldeki önizleme. */
interface LikeDraft {
  listingId: number;
  target: LikeTarget;
  preview: LikePreview;
  recipient: string;
}

const toDeckListing = (a: ApiListing, ownerFallback: string): DeckListing => ({
  id: `api-${a.id}`,
  type: a.type,
  title: a.title,
  description: a.description,
  rent: a.rent ?? undefined,
  budgetMin: a.budget_min ?? undefined,
  budgetMax: a.budget_max ?? undefined,
  district: a.district,
  roomCount: a.room_count ?? undefined,
  photos: a.photos,
  ownerName: a.owner_name ?? ownerFallback,
  source: a,
});

const SwipeScreen = () => {
  const { isLoggedIn, user: me } = useAuth();
  const navigate = useNavigate();
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [cards, setCards] = useState<DeckListing[]>([]);
  const [swipeDirection, setSwipeDirection] = useState<"left" | "right" | null>(null);
  const [filterOpen, setFilterOpen] = useState(false);
  const [resetting, setResetting] = useState(false);
  // Deste sıfırlama ucu sunucuda yalnızca yöneticiye açık; düğmeyi de öyle
  // gösteriyoruz ki kimse kesin 403 alacak bir işlem görmesin.
  const isAdmin = me?.is_admin === true;
  // İstemediklerim sunucuda eler; boş destede kullanıcı sebebini bilsin.
  const hasDealbreakers = (me?.dealbreakers?.length ?? 0) > 0;

  // Rapor kutusu kartın DIŞINDA durur: kart sürüklenirken transform aldığı
  // için içine konan `position: fixed` panel karta göre konumlanır ve ekranı
  // kaplayamaz. Hedef, kutu kapandıktan sonra da tutulur (çıkış animasyonu).
  const [reportTarget, setReportTarget] = useState<{ id: number; title: string } | null>(null);
  const [reportOpen, setReportOpen] = useState(false);
  const openReport = (id: number, title: string) => {
    setReportTarget({ id, title });
    setReportOpen(true);
  };

  // Yorumlu beğeni paneli de aynı sebeple kartın dışında durur.
  const [likeDraft, setLikeDraft] = useState<LikeDraft | null>(null);
  const [likeOpen, setLikeOpen] = useState(false);
  const openLike = (draft: LikeDraft) => {
    setLikeDraft(draft);
    setLikeOpen(true);
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
      ? allListings.filter(l => matchesFilters(l.source, activeFilters))
      : allListings;
    setCards([...base].reverse());
  }, [allListings, activeFilters]);

  // Filtredeki fiyat dağılımı destedeki gerçek ilanlardan çizilir.
  const deckPrices = useMemo(
    () =>
      allListings
        .map(l => listingPrice(l.source))
        .filter((p): p is number => p !== null),
    [allListings],
  );

  // Hiçbir şey seçilmemişse (ör. modaldaki "Temizle") filtre yok sayılır;
  // boş deste metni ve "filtreleri temizle" düğmesi böylece doğru çıkar.
  const applyFilters = (f: ListingFilters) =>
    setActiveFilters(isDefaultFilters(f) ? null : f);

  // Sunucu kararı kaydettikten sonra: önbellek ve eşleşme bildirimi.
  const afterSwipe = useCallback((listingId: number, res: SwipeResult) => {
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
  }, [queryClient, t]);

  // Üstteki kartı mühürle birlikte desteden atar.
  const dismissTop = useCallback((direction: "left" | "right") => {
    setSwipeDirection(direction);
    setTimeout(() => {
      setCards(prev => prev.slice(0, -1));
      setSwipeDirection(null);
    }, 300);
  }, []);

  const handleSwipe = useCallback((direction: "left" | "right") => {
    // Karar sunucuya yalnızca girişliyken ve sunucudaki bir ilan için yazılır.
    const card = cards[cards.length - 1];
    if (card && isLoggedIn && card.id.startsWith("api-")) {
      const listingId = Number(card.id.slice(4));
      postSwipe(listingId, direction === "right" ? "like" : "pass")
        .then(res => afterSwipe(listingId, res))
        // Sunucu kaydırmayı reddedebilir: ilan sahibi askıya alındıysa ya da
        // ilan yayından kalktıysa 404 döner. Sessizce yutmak kullanıcıya
        // kararı kaydedilmiş gibi gösteriyordu; artık sebebini görüyor.
        .catch(err => {
          toast.error(err instanceof Error ? err.message : t("swipe.failed"));
        });
    }
    dismissTop(direction);
  }, [isLoggedIn, cards, afterSwipe, dismissTop, t]);

  // Fotoğrafa / karta yorumlu beğeni. Düz kaydırmanın aksine İYİMSER DEĞİL:
  // kart ancak sunucu beğeniyi kabul edince gider. Yorum denetime takılırsa
  // (422) hata fırlar, panel açık kalır ve yazılan metin kaybolmaz.
  const sendLike = async (comment: string) => {
    if (!likeDraft) return;
    const res = await postSwipe(likeDraft.listingId, "like", {
      target: likeDraft.target,
      comment,
    });
    setLikeOpen(false);
    afterSwipe(likeDraft.listingId, res);
    dismissTop("right");
  };

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
            {hasDealbreakers && (
              <p className="text-sm text-muted-foreground leading-relaxed">
                {t("swipe.emptyDealbreakers")}{" "}
                <button
                  type="button"
                  onClick={() => navigate("/profile/edit")}
                  className="text-secondary font-semibold underline-offset-4 hover:underline"
                >
                  {t("swipe.editDealbreakers")}
                </button>
              </p>
            )}
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
                  direction={swipeDirection}
                  onReport={openReport}
                  onLike={isLoggedIn ? openLike : undefined}
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
      <FilterModal open={filterOpen} onClose={() => setFilterOpen(false)} onApply={applyFilters} prices={deckPrices} />
      {reportTarget && (
        <ReportDialog
          open={reportOpen}
          onClose={() => setReportOpen(false)}
          targetType="listing"
          targetId={reportTarget.id}
          targetLabel={reportTarget.title}
        />
      )}
      <LikeComposer
        open={likeOpen}
        onClose={() => setLikeOpen(false)}
        recipient={likeDraft?.recipient ?? ""}
        preview={likeDraft?.preview ?? null}
        onSend={sendLike}
      />
      <BottomNav />
    </div>
  );
};

/*
 * Kart: Hinge'in profil düzeni. Kapak fotoğrafı, başlık ve fiyat ilk bakışta;
 * kart aşağı kaydırıldıkça ilan yazısı, sonra kart, fotoğraf, kart, fotoğraf…
 * ve en sonda ilan sahibinin öğrenci kartı. Fotoğrafın üstüne yazı basılmaz.
 *
 * Kartın içi dikey kayar, kartın kendisi yatay sürüklenir: iç kaydırıcıdaki
 * `touch-pan-y` dikey hareketi tarayıcıya, yatayı framer-motion'a bırakır.
 *
 * `onLike` verilirse (girişli, üstteki kart) her fotoğrafta ve kartta bir kalp
 * çıkar; kalp yorum panelini açar.
 */
const SwipeCard = ({
  listing,
  isTop = true,
  onLike,
  onReport,
}: {
  listing: DeckListing;
  isTop?: boolean;
  onLike?: (draft: LikeDraft) => void;
  onReport?: (listingId: number, title: string) => void;
}) => {
  const isHouse = listing.type === "ev_ilani";
  const { t, n, locale } = useI18n();
  const apiId = listing.id.startsWith("api-") ? Number(listing.id.slice(4)) : null;
  const src = listing.source;
  const owner = src.owner_profile ?? null;
  const ownerName = listing.ownerName;

  const prompts = listingPrompts(src, { t, n, locale });
  const timeline = interleave(listing.photos.slice(1), prompts, 1);

  // Kalp yalnızca gerçek ilanda ve üstteki kartta.
  const like = apiId !== null && isTop ? onLike : undefined;
  const likeItem = like
    ? (item: TimelineItem) => {
        if (item.kind === "photo") {
          like({
            listingId: apiId!,
            target: { kind: "photo", photo_index: item.index },
            preview: { kind: "photo", url: item.url },
            recipient: ownerName,
          });
        } else if (isLikablePrompt(item.prompt.key)) {
          // Bütçe/semt kartı destede hiç üretilmez; koşul yalnızca tür için.
          like({
            listingId: apiId!,
            target: { kind: "prompt", prompt_key: item.prompt.key },
            preview: { kind: "prompt", ...item.prompt },
            recipient: ownerName,
          });
        }
      }
    : undefined;

  return (
    <div className="card-listing h-full overflow-y-auto overscroll-contain touch-pan-y scrollbar-hide">
      <div className="relative h-[36vh] m-2 mb-0 rounded-xl overflow-hidden bg-muted">
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
        {likeItem && listing.photos[0] && (
          <LikeHeart
            onClick={() => likeItem({ kind: "photo", url: listing.photos[0], index: 0 })}
            className="absolute bottom-3 right-3"
          />
        )}
      </div>

      <div className="px-4 pt-3 pb-5 space-y-3">
        <div>
          <h3 className="font-display text-[1.45rem] leading-tight text-foreground">{listing.title}</h3>
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
                ? `${n(listing.rent ?? 0)} TL`
                : `${n(listing.budgetMin ?? 0)}–${n(listing.budgetMax ?? 0)} TL`}
            </span>
            {isHouse && <span className="text-muted-foreground text-[13px] ml-0.5">{t("common.roomShare")}</span>}
          </p>
          {/* Gerçek ilanlarda modelin adil fiyat kıyası */}
          {isHouse && apiId !== null && isTop && <FairPriceBadge listingId={apiId} />}
        </div>

        {/* İlan sahibinin kendi yazdığı metin: çizgili kâğıtta, beğenilebilir */}
        <div className="relative">
          <p className={`paper-ruled rounded-lg text-[14px] text-foreground whitespace-pre-line ${likeItem ? "pb-14" : ""}`}>
            {listing.description}
          </p>
          {likeItem && (
            <LikeHeart
              onClick={() =>
                like!({
                  listingId: apiId!,
                  target: { kind: "prompt", prompt_key: "description" },
                  preview: { kind: "text", question: t("prompt.q.description"), text: listing.description },
                  recipient: ownerName,
                })
              }
              className="absolute bottom-3 right-3"
            />
          )}
        </div>

        <ProfileTimeline items={timeline} onLike={likeItem} />

        {isHouse && apiId !== null && isTop && <FairPriceBadge listingId={apiId} detailed />}

        {/* İlan sahibi: her yerde aynı öğrenci kartı */}
        {src.owner_id !== null && (
          owner || src.owner_name ? (
            <div className="pt-1 space-y-2">
              <p className="text-[13px] font-semibold text-muted-foreground">{t("swipe.owner")}</p>
              <StudentCard
                name={ownerName}
                photo={owner?.photo}
                university={src.owner_university}
                department={owner?.department}
                year={owner?.year}
                memberNo={src.owner_id}
                verified={!!src.owner_university}
              />
            </div>
          ) : (
            <div className="flex items-center gap-2.5">
              <UserAvatar name={ownerName} photo={owner?.photo ?? undefined} className="w-7 h-7 text-[11px]" />
              <p className="text-[13px] text-muted-foreground truncate">{ownerName}</p>
            </div>
          )
        )}

        {/* Bildirme girişli kullanıcıya açıktır (sunucu 401 döner) */}
        {onReport && apiId !== null && isTop && (
          <button
            onClick={e => {
              e.stopPropagation();
              onReport(apiId, listing.title);
            }}
            className="flex items-center gap-2 text-[13px] font-medium text-muted-foreground hover:text-destructive transition-colors"
          >
            <Flag className="w-3.5 h-3.5" />
            {t("report.reportListing")}
          </button>
        )}
      </div>
    </div>
  );
};

interface SwipeCardDraggableProps {
  listing: DeckListing;
  onSwipe: (dir: "left" | "right") => void;
  direction: "left" | "right" | null;
  /** Kartın altındaki "bu ilanı bildir" bağlantısı. */
  onReport: (listingId: number, title: string) => void;
  /** Girişliyken: fotoğraftaki / karttaki kalp yorum panelini açar. */
  onLike?: (draft: LikeDraft) => void;
}

const SwipeCardDraggable = ({ listing, onSwipe, direction, onReport, onLike }: SwipeCardDraggableProps) => {
  const { t } = useI18n();
  const { isLoggedIn } = useAuth();
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

      <SwipeCard listing={listing} onLike={onLike} onReport={isLoggedIn ? onReport : undefined} />
    </motion.div>
  );
};

export default SwipeScreen;
