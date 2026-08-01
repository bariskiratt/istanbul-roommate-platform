import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import BottomNav from "@/components/layout/BottomNav";
import AppHeader from "@/components/layout/AppHeader";
import { motion } from "framer-motion";
import AuthGate from "@/components/AuthGate";
import { useAuth } from "@/contexts/AuthContext";
import { fetchMatches } from "@/lib/api";
import { parseUtc } from "@/lib/date";
import { useI18n } from "@/i18n";

const placeholderAvatar = "https://api.dicebear.com/9.x/thumbs/svg?seed=roommatch";

// Çözülemeyen mesaj için backend sabit ASCII dize döner (app/crypto.py: UNREADABLE).
// Son mesaj önizlemesinde de ham gösterilmemeli — ChatScreen ile aynı davranış.
const UNREADABLE = "[unreadable]";

const fmtTime = (iso: string | null, locale: string) => {
  if (!iso) return "";
  const d = parseUtc(iso);
  const today = new Date();
  return d.toDateString() === today.toDateString()
    ? d.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString(locale, { day: "numeric", month: "short" });
};

const Messages = () => {
  const navigate = useNavigate();
  const { isLoggedIn } = useAuth();
  const { t, locale } = useI18n();

  const { data: matches = [], isLoading } = useQuery({
    queryKey: ["matches"],
    queryFn: fetchMatches,
    enabled: isLoggedIn,
  });

  return (
    <div className="min-h-screen bg-background pb-20">
      <AppHeader title={t("messages.title")} />

      <div className="px-6 py-4 space-y-3">
        {matches.map((match, i) => {
          const other = match.other_user;
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
                <img
                  src={other.photos[0] ?? placeholderAvatar}
                  alt={other.name}
                  className="w-14 h-14 rounded-full object-cover"
                />
                <div className="absolute bottom-0 right-0 w-3.5 h-3.5 rounded-full bg-accent border-2 border-card" />
              </div>
              <div className="flex-1 min-w-0 text-left">
                <div className="flex items-center justify-between">
                  <p className="font-semibold text-foreground">{other.name || t("messages.unnamed")}</p>
                  <span className="text-xs text-muted-foreground">
                    {fmtTime(match.last_message_at ?? match.created_at, locale)}
                  </span>
                </div>
                <p className="text-sm text-muted-foreground truncate mt-0.5">
                  {match.last_message == null
                    ? t("messages.firstMessage")
                    : match.last_message === UNREADABLE
                      ? t("chat.unreadable")
                      : match.last_message}
                </p>
                {match.listing_title && (
                  <span className="inline-block mt-2 text-[10px] px-2.5 py-1 rounded-full font-medium bg-lavender/50 text-foreground">
                    🏠 {match.listing_title}
                  </span>
                )}
              </div>
            </motion.button>
          );
        })}

        {!isLoading && matches.length === 0 && (
          <div className="text-center py-20 animate-fade-in">
            <div className="w-20 h-20 rounded-3xl bg-lavender/50 flex items-center justify-center mx-auto mb-4">
              <span className="text-3xl">💬</span>
            </div>
            <p className="font-medium text-foreground">{t("messages.emptyTitle")}</p>
            <p className="text-sm text-muted-foreground mt-1">{t("messages.emptyDesc")}</p>
          </div>
        )}
      </div>

      <AuthGate show={!isLoggedIn} onClose={() => {}} />
      <BottomNav />
    </div>
  );
};

export default Messages;
