import { useState, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, useMotionValue, useTransform, AnimatePresence, PanInfo } from "framer-motion";
import { X, Check, Heart, GraduationCap, MapPin, DollarSign, Search, Home } from "lucide-react";
import { toast } from "sonner";
import LifestyleTag from "@/components/LifestyleTag";
import BottomNav from "@/components/layout/BottomNav";
import AppHeader from "@/components/layout/AppHeader";
import { Button } from "@/components/ui/button";
import AuthGate from "@/components/AuthGate";
import { useAuth } from "@/contexts/AuthContext";
import { fetchReceivedLikes, respondToLike, type ReceivedLike } from "@/lib/api";
import { useI18n } from "@/i18n";

const placeholderAvatar = "https://api.dicebear.com/9.x/thumbs/svg?seed=roommatch";

// API beğenisini kart bileşeninin beklediği görünüme çevirir
const toLikeCard = (r: ReceivedLike, unnamed: string) => ({
  id: String(r.swipe_id),
  swipeId: r.swipe_id,
  listingTitle: r.listing_title,
  user: {
    name: r.user.name || unnamed,
    university: r.user.university ?? "—",
    department: r.user.department ?? "—",
    year: r.user.year ?? 0,
    preferredDistrict: r.user.preferred_districts.join(", ") || "—",
    budgetMin: r.user.budget_min ?? 0,
    budgetMax: r.user.budget_max ?? 0,
    smoking: r.user.smoking ?? false,
    pets: r.user.pets ?? false,
    alcohol: r.user.alcohol ?? false,
    sleepSchedule: (r.user.sleep_schedule ?? "esnek") as "erken" | "gece" | "esnek",
    bio: r.user.bio,
    photos: r.user.photos.length > 0 ? r.user.photos : [placeholderAvatar],
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

      {/* Header section */}
      <div className="px-6 pt-4 pb-2">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-foreground">{t("likes.heading")}</h2>
            <p className="text-sm text-muted-foreground mt-0.5">{t("likes.sub")}</p>
          </div>
          {remaining > 0 && (
            <span className="px-3 py-1.5 rounded-full text-xs font-bold bg-destructive/15 text-destructive">
              {t("likes.new", { count: remaining })}
            </span>
          )}
        </div>
      </div>

      {/* Card area */}
      <div className="flex-1 relative flex items-center justify-center px-6 pt-2">
        {remaining === 0 && !matchPopup ? (
          <div className="text-center space-y-4 animate-fade-in">
            <div className="w-24 h-24 rounded-3xl bg-lavender/50 flex items-center justify-center mx-auto">
              <div className="relative">
                <Home className="w-10 h-10 text-primary" />
                <Search className="w-5 h-5 text-primary absolute -bottom-1 -right-1" />
              </div>
            </div>
            <h2 className="text-xl font-bold text-foreground">{t("likes.emptyTitle")}</h2>
            <p className="text-sm text-muted-foreground max-w-[260px] mx-auto">
              {t("likes.emptyDesc")}
            </p>
          </div>
        ) : currentProfile ? (
          <div className="relative w-full max-w-sm" style={{ height: '62vh' }}>
            {/* Counter */}
            <div className="absolute -top-1 right-0 z-10 text-xs font-medium text-muted-foreground">
              {total - remaining + 1} / {total}
            </div>

            {/* Next card preview */}
            {nextProfile && (
              <div className="absolute inset-x-2 top-3 bottom-0 scale-[0.95] opacity-50 rounded-2xl overflow-hidden">
                <div className="card-listing h-full bg-card" />
              </div>
            )}

            {/* Current card */}
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

      {/* Action buttons */}
      {remaining > 0 && (
        <div className="flex items-center justify-center gap-12 py-4">
          <div className="flex flex-col items-center gap-1.5">
            <button
              onClick={() => handleDecision("left")}
              className="w-16 h-16 rounded-full bg-card flex items-center justify-center text-destructive transition-all active:scale-95"
              style={{ boxShadow: '0 4px 16px hsl(6 100% 69% / 0.25)' }}
            >
              <X className="w-7 h-7" strokeWidth={2.5} />
            </button>
            <span className="text-[11px] text-muted-foreground font-medium">{t("likes.pass")}</span>
          </div>
          <div className="flex flex-col items-center gap-1.5">
            <button
              onClick={() => handleDecision("right")}
              className="w-16 h-16 rounded-full bg-card flex items-center justify-center text-accent transition-all active:scale-95"
              style={{ boxShadow: '0 4px 16px hsl(165 70% 58% / 0.25)' }}
            >
              <Check className="w-7 h-7" strokeWidth={2.5} />
            </button>
            <span className="text-[11px] text-muted-foreground font-medium">{t("likes.match")}</span>
          </div>
        </div>
      )}

      {/* Match celebration overlay */}
      <AnimatePresence>
        {matchPopup && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center"
          >
            <div className="absolute inset-0 gradient-hero" />
            <div className="absolute inset-0 bg-foreground/20" />

            <motion.div
              initial={{ scale: 0.5, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.5, opacity: 0 }}
              transition={{ type: "spring", damping: 20 }}
              className="relative z-10 text-center space-y-6 w-full max-w-sm px-6"
            >
              <motion.p
                initial={{ y: -20, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ delay: 0.2 }}
                className="text-5xl"
              >
                🎉
              </motion.p>
              <h2 className="text-3xl font-extrabold text-foreground">{t("likes.matched")}</h2>

              <div className="flex items-center justify-center">
                <motion.img
                  initial={{ x: -40, opacity: 0 }}
                  animate={{ x: 0, opacity: 1 }}
                  transition={{ delay: 0.3 }}
                  src={me?.photos[0] ?? placeholderAvatar}
                  alt=""
                  className="w-20 h-20 rounded-full object-cover border-4 border-card shadow-lg"
                />
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: 0.5 }}
                  className="w-10 h-10 rounded-full bg-accent flex items-center justify-center -mx-3 z-10 shadow-lg"
                >
                  <Heart className="w-5 h-5 text-accent-foreground" />
                </motion.div>
                <motion.img
                  initial={{ x: 40, opacity: 0 }}
                  animate={{ x: 0, opacity: 1 }}
                  transition={{ delay: 0.3 }}
                  src={matchPopup.user.photos[0]}
                  alt=""
                  className="w-20 h-20 rounded-full object-cover border-4 border-card shadow-lg"
                />
              </div>

              <p className="text-muted-foreground text-sm">
                {t("likes.matchedWith", { name: matchPopup.user.name })}
              </p>

              <div className="space-y-3 pt-2">
                <Button
                  onClick={() => {
                    setMatchPopup(null);
                    navigate("/messages");
                  }}
                  className="w-full h-14 bg-gradient-to-r from-primary to-secondary text-primary-foreground shadow-lg font-bold text-base"
                >
                  {t("likes.sendMessage")}
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => setMatchPopup(null)}
                  className="w-full h-12 text-foreground font-medium"
                >
                  {t("likes.keepExploring")}
                </Button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Confetti */}
      {confetti && (
        <div className="fixed inset-0 z-40 pointer-events-none overflow-hidden">
          {Array.from({ length: 40 }).map((_, i) => (
            <div
              key={i}
              className="absolute w-3 h-3 animate-confetti"
              style={{
                left: `${Math.random() * 100}%`,
                top: `-${Math.random() * 20}%`,
                animationDelay: `${Math.random() * 0.5}s`,
                animationDuration: `${1 + Math.random() * 1}s`,
                backgroundColor: [
                  "hsl(var(--lavender))",
                  "hsl(var(--mint))",
                  "hsl(var(--primary))",
                  "hsl(var(--sand))",
                  "hsl(var(--coral) / 0.5)",
                ][Math.floor(Math.random() * 5)],
                borderRadius: Math.random() > 0.5 ? "50%" : "2px",
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

/* Draggable profile card */
interface ProfileCardProps {
  notification: LikeCard;
  onSwipe: (dir: "left" | "right") => void;
  direction: "left" | "right" | null;
}

const ProfileCard = ({ notification, onSwipe, direction }: ProfileCardProps) => {
  const { user } = notification;
  const { t, n } = useI18n();
  const x = useMotionValue(0);
  const rotate = useTransform(x, [-200, 200], [-12, 12]);
  const acceptOpacity = useTransform(x, [0, 100], [0, 1]);
  const rejectOpacity = useTransform(x, [-100, 0], [1, 0]);

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
      {/* Swipe labels */}
      <motion.div
        className="absolute top-8 right-6 z-10 bg-accent/90 backdrop-blur-sm text-accent-foreground px-5 py-2.5 rounded-2xl font-bold text-xl rotate-[-15deg]"
        style={{ opacity: acceptOpacity }}
      >
        {t("likes.matchLabel")}
      </motion.div>
      <motion.div
        className="absolute top-8 left-6 z-10 bg-destructive/90 backdrop-blur-sm text-destructive-foreground px-5 py-2.5 rounded-2xl font-bold text-xl rotate-[15deg]"
        style={{ opacity: rejectOpacity }}
      >
        {t("likes.passLabel")}
      </motion.div>

      <div className="card-listing h-full flex flex-col">
        {/* Photo — top 55% */}
        <div className="relative flex-[0_0_55%] overflow-hidden rounded-t-2xl">
          <img src={user.photos[0]} alt={user.name} className="w-full h-full object-cover object-top" />
          <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/70 via-black/30 to-transparent p-5 pt-16">
            <h3 className="font-bold text-2xl text-white leading-tight">{user.name}</h3>
            <div className="flex items-center gap-1.5 mt-1 text-white/90 text-sm">
              <GraduationCap className="w-4 h-4" />
              {user.university}
            </div>
          </div>
        </div>

        {/* Info — bottom */}
        <div className="p-5 flex-1 space-y-3 overflow-y-auto">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <GraduationCap className="w-4 h-4" />
            <span>{user.university} · {user.department}</span>
          </div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <MapPin className="w-4 h-4" />
            <span>{user.preferredDistrict} · {t("likes.year", { year: user.year })}</span>
          </div>

          {/* Budget pill */}
          <div className="inline-flex items-center gap-1.5 bg-accent/15 rounded-full px-3 py-1.5">
            <DollarSign className="w-3.5 h-3.5 text-accent" />
            <span className="text-xs font-bold text-foreground">
              {n(user.budgetMin)} — {n(user.budgetMax)} ₺
            </span>
          </div>

          {/* Lifestyle tags */}
          <div className="flex flex-wrap gap-1.5">
            <LifestyleTag type="smoking" value={user.smoking} />
            <LifestyleTag type="pets" value={user.pets} />
            <LifestyleTag type="alcohol" value={user.alcohol} />
            <LifestyleTag type="sleep" value={user.sleepSchedule} />
          </div>

          {/* Note */}
          <p className="text-xs text-muted-foreground italic">
            {t("likes.interested", { title: notification.listingTitle })}
          </p>

          {/* Bio */}
          {user.bio && (
            <p className="text-sm text-muted-foreground leading-relaxed line-clamp-2">
              "{user.bio}"
            </p>
          )}
        </div>
      </div>
    </motion.div>
  );
};

export default Matches;
