import { useNavigate } from "react-router-dom";
import { mockMatches } from "@/data/mockData";
import BottomNav from "@/components/layout/BottomNav";
import AppHeader from "@/components/layout/AppHeader";
import { motion } from "framer-motion";
import AuthGate from "@/components/AuthGate";
import { useAuth } from "@/contexts/AuthContext";

const Messages = () => {
  const navigate = useNavigate();
  const { isLoggedIn } = useAuth();

  return (
    <div className="min-h-screen bg-background pb-20">
      <AppHeader title="Mesajlar" />

      <div className="px-6 py-4 space-y-3">
        {mockMatches.map((match, i) => {
          const other = match.userB;
          const hasUnread = match.unreadCount > 0;
          return (
            <motion.button
              key={match.id}
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: i * 0.05 }}
              onClick={() => navigate(`/chat/${match.id}`)}
              className="w-full card-listing p-5 flex items-center gap-4 hover:shadow-lg transition-shadow"
            >
              <div className="relative flex-shrink-0">
                <img src={other.photos[0]} alt={other.name} className="w-14 h-14 rounded-full object-cover" />
                <div className="absolute bottom-0 right-0 w-3.5 h-3.5 rounded-full bg-accent border-2 border-card" />
                {hasUnread && <div className="absolute -top-0.5 -right-0.5 w-3 h-3 rounded-full bg-primary" />}
              </div>
              <div className="flex-1 min-w-0 text-left">
                <div className="flex items-center justify-between">
                  <p className={`font-semibold text-foreground ${hasUnread ? "font-bold" : ""}`}>{other.name}</p>
                  <span className="text-xs text-muted-foreground">{match.lastMessageTime}</span>
                </div>
                <p className="text-sm text-muted-foreground truncate mt-0.5">{match.lastMessage}</p>
                <span className={`inline-block mt-2 text-[10px] px-2.5 py-1 rounded-full font-medium ${
                  match.matchType === "ev_kisi" ? "bg-lavender/50 text-foreground" : "bg-accent/15 text-foreground"
                }`}>
                  {match.matchType === "ev_kisi" ? "🏠 Ev Eşleşmesi" : "👥 Kişi Eşleşmesi"}
                </span>
              </div>
            </motion.button>
          );
        })}

        {mockMatches.length === 0 && (
          <div className="text-center py-20 animate-fade-in">
            <div className="w-20 h-20 rounded-3xl bg-lavender/50 flex items-center justify-center mx-auto mb-4">
              <span className="text-3xl">💬</span>
            </div>
            <p className="font-medium text-foreground">Henüz mesajın yok</p>
            <p className="text-sm text-muted-foreground mt-1">Eşleştiğinde burada görünecek</p>
          </div>
        )}
      </div>

      <AuthGate show={!isLoggedIn} onClose={() => {}} />
      <BottomNav />
    </div>
  );
};

export default Messages;
