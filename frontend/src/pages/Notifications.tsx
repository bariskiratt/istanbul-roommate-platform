import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Heart, GraduationCap, DollarSign, MessageCircle, ArrowRight } from "lucide-react";
import { mockSwipeNotifications, type SwipeNotification } from "@/data/mockData";
import LifestyleTag from "@/components/LifestyleTag";
import BottomNav from "@/components/layout/BottomNav";
import AppHeader from "@/components/layout/AppHeader";
import { Button } from "@/components/ui/button";
import AuthGate from "@/components/AuthGate";
import { useAuth } from "@/contexts/AuthContext";

const Notifications = () => {
  const { isLoggedIn } = useAuth();
  const [notifications, setNotifications] = useState(mockSwipeNotifications);
  const [matchPopup, setMatchPopup] = useState<SwipeNotification | null>(null);
  const [confetti, setConfetti] = useState(false);

  const handleSwipe = (notifId: string, direction: "left" | "right") => {
    const notif = notifications.find(n => n.id === notifId);
    if (direction === "right" && notif) {
      setMatchPopup(notif);
      setConfetti(true);
      setTimeout(() => setConfetti(false), 2000);
    }
    setNotifications(prev => prev.filter(n => n.id !== notifId));
  };

  const groupedByListing = notifications.reduce((acc, notif) => {
    if (!acc[notif.listingTitle]) acc[notif.listingTitle] = [];
    acc[notif.listingTitle].push(notif);
    return acc;
  }, {} as Record<string, SwipeNotification[]>);

  return (
    <div className="min-h-screen bg-background pb-20">
      <AppHeader title="Bildirimler" />

      <div className="px-6 py-4 space-y-6">
        {Object.entries(groupedByListing).map(([listingTitle, notifs]) => (
          <div key={listingTitle} className="space-y-3 animate-fade-in">
            {/* Listing group header — white card with left accent bar */}
            <div className="card-listing p-4 flex items-center gap-3 border-l-4 border-l-primary">
              <div>
                <p className="text-sm font-bold text-foreground">🏠 {listingTitle}</p>
                <p className="text-xs text-primary font-medium">{notifs.length} kişi evinizi beğendi</p>
              </div>
            </div>

            {notifs.map(notif => (
              <NotificationCard
                key={notif.id}
                notification={notif}
                onSwipe={(dir) => handleSwipe(notif.id, dir)}
              />
            ))}
          </div>
        ))}

        {notifications.length === 0 && !matchPopup && (
          <div className="text-center py-20 animate-fade-in">
            <div className="w-20 h-20 rounded-3xl bg-lavender/50 flex items-center justify-center mx-auto mb-4">
              <Heart className="w-10 h-10 text-primary" />
            </div>
            <p className="text-muted-foreground font-medium">Henüz yeni bildirim yok</p>
          </div>
        )}
      </div>

      {/* Match popup — full-screen modal with radial gradient */}
      <AnimatePresence>
        {matchPopup && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center"
            onClick={() => setMatchPopup(null)}
          >
            {/* Background gradient */}
            <div className="absolute inset-0 gradient-hero" />
            <div className="absolute inset-0 bg-foreground/20" />
            
            <motion.div
              initial={{ scale: 0.5, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.5, opacity: 0 }}
              transition={{ type: "spring", damping: 20 }}
              className="relative z-10 text-center space-y-6 w-full max-w-sm px-6"
              onClick={e => e.stopPropagation()}
            >
              <motion.p
                initial={{ y: -20, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ delay: 0.2 }}
                className="text-5xl"
              >
                🎉
              </motion.p>
              <h2 className="text-3xl font-extrabold text-foreground">Eşleştin!</h2>
              
              {/* Avatar merge */}
              <div className="flex items-center justify-center gap-[-8px]">
                <motion.img
                  initial={{ x: -40, opacity: 0 }}
                  animate={{ x: 0, opacity: 1 }}
                  transition={{ delay: 0.3 }}
                  src={matchPopup.user.photos[0]}
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
                  src="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=200&h=200&fit=crop&crop=face"
                  alt=""
                  className="w-20 h-20 rounded-full object-cover border-4 border-card shadow-lg"
                />
              </div>

              <p className="text-muted-foreground text-sm">
                {matchPopup.user.name} ile eşleştin! Artık mesajlaşabilirsiniz.
              </p>
              
              <div className="space-y-3 pt-2">
                <Button
                  onClick={() => setMatchPopup(null)}
                  className="w-full h-14 bg-gradient-to-r from-primary to-secondary text-primary-foreground shadow-lg font-bold text-base"
                >
                  <MessageCircle className="w-5 h-5 mr-2" />
                  Mesaj Gönder
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => setMatchPopup(null)}
                  className="w-full h-12 text-foreground font-medium"
                >
                  Keşfetmeye Devam Et
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Confetti — pastel colors */}
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

const NotificationCard = ({ notification, onSwipe }: { notification: SwipeNotification; onSwipe: (dir: "left" | "right") => void }) => {
  const { user } = notification;
  return (
    <div className="card-listing p-5 flex items-center gap-4">
      <img src={user.photos[0]} alt={user.name} className="w-14 h-14 rounded-full object-cover" />
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-foreground truncate">{user.name}</p>
        <div className="flex items-center gap-2 text-xs text-muted-foreground mt-0.5">
          <GraduationCap className="w-3.5 h-3.5" />
          {user.university}
        </div>
        <div className="flex items-center gap-1 text-xs text-muted-foreground mt-0.5">
          <DollarSign className="w-3.5 h-3.5" />
          {user.budgetMin.toLocaleString("tr-TR")} — {user.budgetMax.toLocaleString("tr-TR")} ₺
        </div>
        <div className="flex flex-wrap gap-1 mt-2">
          <LifestyleTag type="smoking" value={user.smoking} compact />
          <LifestyleTag type="pets" value={user.pets} compact />
          <LifestyleTag type="sleep" value={user.sleepSchedule} compact />
        </div>
      </div>
      <div className="flex flex-col gap-2">
        <button onClick={() => onSwipe("right")} className="w-12 h-12 rounded-full bg-accent/10 text-accent flex items-center justify-center hover:bg-accent hover:text-accent-foreground transition-all hover:shadow-md active:scale-95">
          <Heart className="w-5 h-5" />
        </button>
        <button onClick={() => onSwipe("left")} className="w-12 h-12 rounded-full bg-destructive/10 text-destructive flex items-center justify-center hover:bg-destructive hover:text-destructive-foreground transition-all hover:shadow-md active:scale-95">
          <X className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
};

export default Notifications;
