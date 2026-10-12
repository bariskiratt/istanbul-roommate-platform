import { useState, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, useMotionValue, useTransform, AnimatePresence, PanInfo } from "framer-motion";
import { X, Check } from "lucide-react";
import { toast } from "sonner";
import BottomNav from "@/components/layout/BottomNav";
import AppHeader from "@/components/layout/AppHeader";
import { Button } from "@/components/ui/button";
import AuthGate from "@/components/AuthGate";
import StudentCard from "@/components/campus/StudentCard";
import ProfileTimeline from "@/components/campus/ProfileTimeline";
import LikeContext from "@/components/LikeContext";
import { useAuth } from "@/contexts/AuthContext";
import { fetchReceivedLikes, respondToLike, type ReceivedLike } from "@/lib/api";
import { interleave, personPrompts } from "@/lib/prompts";
import { useI18n } from "@/i18n";

// API beğenisini kart bileşeninin beklediği görünüme çevirir
const toLikeCard = (r: ReceivedLike, unnamed: string) => ({
  id: String(r.swipe_id),
  swipeId: r.swipe_id,
  listingTitle: r.listing_title,
  // Sunucudaki hâli: neyin beğenildiği, yorum ve kartların kaynağı.
  raw: r,
  user: {
    id: r.user.id,
    // Ham üniversite: öğrenci kartındaki mühür yalnızca bu doluysa basılır
    rawUniversity: r.user.university,
    rawDepartment: r.user.department,
    name: r.user.name || unnamed,
    year: r.user.year ?? 0,
    bio: r.user.bio,
    photos: r.user.photos,
  },
});

type LikeCard = ReturnType<typeof toLikeCard>;

const Matches = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { isLoggedIn, user: me } = useAuth();
  const { t } = useI18n();
  const [queue, setQueue] = useState<LikeCard[]>([]);
  const [matchPopup, setMatchPopup] = useState<LikeCard | null>(null);
  const [confetti, setConfetti] = useState(false);
  const [swipeDir, setSwipeDir] = useState<"left" | "right" | null>(null);

  const { data: received = [] } = useQuery({
    queryKey: ["received-likes"],
    queryFn: fetchReceivedLikes,
    enabled: isLoggedIn,
  });

  const unnamed = t("messages.unnamed");
  useEffect(() => {
    setQueue(received.map(r => toLikeCard(r, unnamed)));
  }, [received, unnamed]);

  const total = received.length;
  const remaining = queue.length;

  const handleDecision = useCallback((direction: "left" | "right") => {
    const current = queue[0];
    if (!current) return;

    respondToLike(current.swipeId, direction === "right")
      .then(res => {
        // Cache tazelenmezse yeniden fetch'te cevaplanmış beğeniler geri gelir
        queryClient.invalidateQueries({ queryKey: ["received-likes"] });
        queryClient.invalidateQueries({ queryKey: ["matches"] });
        if (res.matched) {
          setMatchPopup(current);
          setConfetti(true);
          setTimeout(() => setConfetti(false), 2000);
        }
      })
      .catch(err =>
        toast.error(err instanceof Error ? err.message : t("likes.responseFailed")),
      );

    setSwipeDir(direction);
    setTimeout(() => {
      setQueue(prev => prev.slice(1));
      setSwipeDir(null);
    }, 300);
  }, [queue, queryClient, t]);

  const currentProfile = queue[0];
  const nextProfile = queue[1];

  return (
    <div className="min-h-screen bg-background flex flex-col pb-20">
      <AppHeader title={t("likes.title")} />

      <div className="px-5 pt-5 pb-1 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl text-foreground">{t("likes.heading")}</h2>
          <p className="text-sm text-muted-foreground mt-1">{t("likes.sub")}</p>
        </div>
        {remaining > 0 && (
          <span className="shrink-0 mt-1 px-3 py-1 rounded-full text-[12px] font-semibold bg-primary text-primary-foreground">
            {t("likes.new", { count: remaining })}
          </span>
        )}
      </div>

      <div className="flex-1 relative flex items-center justify-center px-4 pt-3">
        {remaining === 0 && !matchPopup ? (
          <div className="w-full max-w-sm px-2 space-y-3 animate-fade-in">
            <h2 className="text-[2rem] leading-tight text-foreground">{t("likes.emptyTitle")}</h2>
            <p className="text-muted-foreground leading-relaxed">{t("likes.emptyDesc")}</p>
          </div>
        ) : currentProfile ? (
          <div className="relative w-full max-w-sm" style={{ height: '62vh' }}>
            <div className="absolute -top-6 right-1 z-10 text-[12px] text-muted-foreground tabular-nums">
              {total - remaining + 1} / {total}
            </div>
            {nextProfile && (
              <div className="absolute inset-0 translate-y-2 scale-[0.96] rounded-2xl border border-border bg-card" aria-hidden="true" />
            )}
            <AnimatePresence>
              <ProfileCard
                key={currentProfile.id}
                notification={currentProfile}
                onSwipe={handleDecision}
                direction={swipeDir}
              />
            </AnimatePresence>
          </div>
        ) : null}
      </div>

      {remaining > 0 && (
        <div className="flex items-start justify-center gap-10 py-4">
          <div className="flex flex-col items-center gap-1.5">
            <button
              onClick={() => handleDecision("left")}
              aria-label={t("likes.pass")}
              className="btn-swipe-pass w-16 h-16 flex items-center justify-center"
            >
              <X className="w-7 h-7" strokeWidth={2.4} />
            </button>
            <span className="text-[12px] text-muted-foreground font-medium">{t("likes.pass")}</span>
          </div>
          <div className="flex flex-col items-center gap-1.5">
            <button
              onClick={() => handleDecision("right")}
              aria-label={t("likes.match")}
              className="btn-swipe-like w-16 h-16 flex items-center justify-center"
            >
              <Check className="w-7 h-7" strokeWidth={2.4} />
            </button>
            <span className="text-[12px] text-muted-foreground font-medium">{t("likes.match")}</span>
          </div>
        </div>
      )}

      {/* Eşleşme anı: karşıdakinin kartı, üstünde "eşleşti" mührü */}
      <AnimatePresence>
        {matchPopup && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-background/95 backdrop-blur-sm"
          >
            <motion.div
              initial={{ y: 24, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: 24, opacity: 0 }}
              transition={{ type: "spring", damping: 22 }}
              className="relative w-full max-w-sm px-6 space-y-6"
            >
              <h2 className="text-5xl leading-none text-foreground">{t("likes.matched")}</h2>
              <div className="relative">
                <StudentCard
                  name={matchPopup.user.name}
                  photo={matchPopup.user.photos[0]}
                  university={matchPopup.user.rawUniversity}
                  department={matchPopup.user.rawDepartment}
                  year={matchPopup.user.year || null}
                  memberNo={matchPopup.user.id}
                  className="rotate-[-1.5deg]"
                />
                <motion.span
                  initial={{ scale: 1.8, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ delay: 0.35, duration: 0.25 }}
                  className="absolute -bottom-4 right-3 rotate-[-10deg]"
                >
                  <span className="stamp text-2xl px-4 py-1.5 bg-card/80">{t("likes.matchStamp")}</span>
                </motion.span>
              </div>
              <p className="text-muted-foreground pt-2">
                {t("likes.matchedWith", { name: matchPopup.user.name })}
              </p>
              <div className="space-y-2">
                <Button
                  size="lg"
                  onClick={() => {
                    setMatchPopup(null);
                    navigate("/messages");
                  }}
                  className="w-full h-12 text-base"
                >
                  {t("likes.sendMessage")}
                </Button>
                <Button variant="ghost" size="lg" onClick={() => setMatchPopup(null)} className="w-full h-12">
                  {t("likes.keepExploring")}
                </Button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Delgeç konfetisi: kâğıttan delinmiş yuvarlaklar */}
      {confetti && (
        <div className="fixed inset-0 z-[60] pointer-events-none overflow-hidden" aria-hidden="true">
          {Array.from({ length: 36 }).map((_, i) => (
            <div
              key={i}
              className="absolute w-2.5 h-2.5 rounded-full animate-confetti"
              style={{
                left: `${Math.random() * 100}%`,
                top: `-${Math.random() * 20}%`,
                animationDelay: `${Math.random() * 0.5}s`,
                animationDuration: `${1 + Math.random() * 1}s`,
                backgroundColor: [
                  "hsl(var(--highlighter))",
                  "hsl(var(--secondary))",
                  "hsl(var(--accent))",
                  "hsl(var(--card))",
                ][i % 4],
                border: "1px solid hsl(var(--border))",
              }}
            />
          ))}
        </div>
      )}

      <AuthGate show={!isLoggedIn} onClose={() => {}} />
      <BottomNav />
    </div>
  );
};

/*
 * Sürüklenebilir profil, Hinge düzeninde: önce NEYİ beğendiği ve yorumu, sonra
 * öğrenci kartı, sonra kart, fotoğraf, kart… ve en sonda kendi yazdığı bio.
 */
interface ProfileCardProps {
  notification: LikeCard;
  onSwipe: (dir: "left" | "right") => void;
  direction: "left" | "right" | null;
}

const ProfileCard = ({ notification, onSwipe, direction }: ProfileCardProps) => {
  const { user, raw } = notification;
  const { t, n, locale } = useI18n();
  const x = useMotionValue(0);
  const rotate = useTransform(x, [-200, 200], [-10, 10]);
  const acceptOpacity = useTransform(x, [0, 100], [0, 1]);
  const rejectOpacity = useTransform(x, [-100, 0], [1, 0]);

  // Kapak fotoğrafı öğrenci kartında; kalanlar kartların arasına girer.
  const timeline = interleave(raw.user.photos.slice(1), personPrompts(raw.user, { t, n, locale }), 1);

  const handleDragEnd = (_: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
    if (info.offset.x > 100) onSwipe("right");
    else if (info.offset.x < -100) onSwipe("left");
  };

  const exitX = direction === "right" ? 500 : direction === "left" ? -500 : 0;

  return (
    <motion.div
      className="absolute inset-0 cursor-grab active:cursor-grabbing swipe-card"
      style={{ x, rotate }}
      drag="x"
      dragConstraints={{ left: 0, right: 0 }}
      dragElastic={0.7}
      onDragEnd={handleDragEnd}
      animate={direction ? { x: exitX, opacity: 0 } : {}}
      transition={{ duration: 0.3 }}
    >
      <motion.div className="absolute top-24 left-6 z-10 -rotate-[14deg] pointer-events-none" style={{ opacity: acceptOpacity }}>
        <span className="stamp text-2xl px-4 py-1.5 bg-card/80">{t("likes.matchLabel")}</span>
      </motion.div>
      <motion.div className="absolute top-24 right-6 z-10 rotate-[14deg] pointer-events-none" style={{ opacity: rejectOpacity }}>
        <span className="stamp stamp-red text-2xl px-4 py-1.5 bg-card/80">{t("likes.passLabel")}</span>
      </motion.div>

      {/* İç kaydırıcı dikey kayar, kart yatay sürüklenir (touch-pan-y). */}
      <div className="h-full rounded-2xl border border-border bg-card p-3 space-y-4 overflow-y-auto overscroll-contain touch-pan-y scrollbar-hide">
        <div className="px-1 pt-1">
          <LikeContext like={raw} />
        </div>

        <StudentCard
          name={user.name}
          photo={user.photos[0]}
          university={user.rawUniversity}
          department={user.rawDepartment}
          year={user.year || null}
          memberNo={user.id}
          verified={!!user.rawUniversity}
        />

        <ProfileTimeline items={timeline} />

        {user.bio && (
          <p className="paper-ruled rounded-lg text-[14px] text-foreground whitespace-pre-line">{user.bio}</p>
        )}
      </div>
    </motion.div>
  );
};

export default Matches;
