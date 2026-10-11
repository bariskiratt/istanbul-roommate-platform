import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { X, Heart } from "lucide-react";
import { toast } from "sonner";
import LifestyleTag from "@/components/LifestyleTag";
import BottomNav from "@/components/layout/BottomNav";
import AppHeader from "@/components/layout/AppHeader";
import { Button } from "@/components/ui/button";
import AuthGate from "@/components/AuthGate";
import UserAvatar from "@/components/UserAvatar";
import StudentCard from "@/components/campus/StudentCard";
import { useAuth } from "@/contexts/AuthContext";
import { fetchReceivedLikes, respondToLike, type ReceivedLike } from "@/lib/api";
import { useI18n } from "@/i18n";

// API beğenisini kartın beklediği görünüme çevirir
const toNotification = (r: ReceivedLike, unnamed: string) => ({
  id: String(r.swipe_id),
  swipeId: r.swipe_id,
  listingTitle: r.listing_title,
  user: {
    id: r.user.id,
    name: r.user.name || unnamed,
    university: r.user.university ?? "—",
    rawUniversity: r.user.university,
    rawDepartment: r.user.department,
    year: r.user.year,
    budgetMin: r.user.budget_min ?? 0,
    budgetMax: r.user.budget_max ?? 0,
    smoking: r.user.smoking ?? false,
    pets: r.user.pets ?? false,
    sleepSchedule: (r.user.sleep_schedule ?? "esnek") as "erken" | "gece" | "esnek",
    photos: r.user.photos,
  },
});

type Notification = ReturnType<typeof toNotification>;

const Notifications = () => {
  const { isLoggedIn, user: me } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [matchPopup, setMatchPopup] = useState<Notification | null>(null);
  const [confetti, setConfetti] = useState(false);

  const { data: received = [] } = useQuery({
    queryKey: ["received-likes"],
    queryFn: fetchReceivedLikes,
    enabled: isLoggedIn,
  });

  const unnamed = t("messages.unnamed");
  useEffect(() => {
    setNotifications(received.map(r => toNotification(r, unnamed)));
  }, [received, unnamed]);

  const handleSwipe = (notifId: string, direction: "left" | "right") => {
    const notif = notifications.find(n => n.id === notifId);
    if (!notif) return;

    respondToLike(notif.swipeId, direction === "right")
      .then(res => {
        queryClient.invalidateQueries({ queryKey: ["received-likes"] });
        queryClient.invalidateQueries({ queryKey: ["matches"] });
        if (res.matched) {
          setMatchPopup(notif);
          setConfetti(true);
          setTimeout(() => setConfetti(false), 2000);
        }
      })
      .catch(err =>
        toast.error(err instanceof Error ? err.message : t("likes.responseFailed")),
      );

    setNotifications(prev => prev.filter(n => n.id !== notifId));
  };

  const groupedByListing = notifications.reduce((acc, notif) => {
    if (!acc[notif.listingTitle]) acc[notif.listingTitle] = [];
    acc[notif.listingTitle].push(notif);
    return acc;
  }, {} as Record<string, Notification[]>);

  return (
    <div className="min-h-screen bg-background pb-24">
      <AppHeader title={t("notif.title")} />

      <div className="px-5 py-5 space-y-8 max-w-lg mx-auto">
        {Object.entries(groupedByListing).map(([listingTitle, notifs]) => (
          <section key={listingTitle} className="space-y-3">
            {/* Grup başlığı: hangi ilanın beğenildiği */}
            <div>
              <h2 className="text-xl text-foreground leading-snug">{listingTitle}</h2>
              <p className="text-[13px] text-muted-foreground mt-0.5">
                {t("notif.likedYourHouse", { count: notifs.length })}
              </p>
            </div>

            <ul className="rounded-2xl border border-border divide-y divide-border">
              {notifs.map(notif => (
                <NotificationCard
                  key={notif.id}
                  notification={notif}
                  onSwipe={(dir) => handleSwipe(notif.id, dir)}
                />
              ))}
            </ul>
          </section>
        ))}

        {notifications.length === 0 && !matchPopup && (
          <div className="py-16 space-y-2">
            <p className="font-display text-2xl text-foreground">{t("notif.empty")}</p>
            <Button variant="outline" onClick={() => navigate("/swipe")}>{t("likes.keepExploring")}</Button>
          </div>
        )}
      </div>

      {/* Eşleşme anı: Beğeniler sayfasıyla aynı, karşıdakinin kartı ve mühür */}
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
                  year={matchPopup.user.year}
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
                  onClick={() => { setMatchPopup(null); navigate("/messages"); }}
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

const NotificationCard = ({ notification, onSwipe }: { notification: Notification; onSwipe: (dir: "left" | "right") => void }) => {
  const { user } = notification;
  const { t, n } = useI18n();
  return (
    <li className="p-4 flex items-center gap-4">
      <UserAvatar name={user.name} photo={user.photos[0]} className="w-14 h-14 text-lg" />
      <div className="flex-1 min-w-0">
        <p className="font-display text-lg font-semibold leading-tight text-foreground truncate">{user.name}</p>
        <p className="text-[13px] text-muted-foreground truncate">{user.university}</p>
        <p className="text-[13px] mt-0.5">
          <span className="marker font-semibold">{n(user.budgetMin)}–{n(user.budgetMax)} ₺</span>
        </p>
        <div className="flex flex-wrap gap-1 mt-2">
          <LifestyleTag type="smoking" value={user.smoking} compact />
          <LifestyleTag type="pets" value={user.pets} compact />
          <LifestyleTag type="sleep" value={user.sleepSchedule} compact />
        </div>
      </div>
      <div className="flex flex-col gap-2">
        <button
          onClick={() => onSwipe("right")}
          aria-label={t("swipe.like")}
          className="btn-swipe-like w-11 h-11 flex items-center justify-center"
        >
          <Heart className="w-5 h-5" />
        </button>
        <button
          onClick={() => onSwipe("left")}
          aria-label={t("swipe.pass")}
          className="btn-swipe-pass w-11 h-11 flex items-center justify-center"
        >
          <X className="w-5 h-5" />
        </button>
      </div>
    </li>
  );
};

export default Notifications;
