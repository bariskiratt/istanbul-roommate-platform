import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import BottomNav from "@/components/layout/BottomNav";
import AppHeader from "@/components/layout/AppHeader";
import AuthGate from "@/components/AuthGate";
import UserAvatar from "@/components/UserAvatar";
import { useAuth } from "@/contexts/AuthContext";
import { REMOVED_CONTENT, UNREADABLE_CONTENT, fetchMatches } from "@/lib/api";
import { parseUtc } from "@/lib/date";
import { useI18n } from "@/i18n";

// Çözülemeyen ("[unreadable]") ve moderasyonca kaldırılmış
// ("[removed_by_moderation]") mesajlar için backend sabit ASCII dize döner.
// Son mesaj önizlemesinde de ham gösterilmemeli — ChatScreen ile aynı davranış.

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

      {/* Hinge'in sohbet listesi gibi: kart yok, ince çizgiyle ayrılmış satırlar */}
      <div className="px-5">
        <ul className="divide-y divide-border">
          {matches.map(match => {
            const other = match.other_user;
            return (
              <li key={match.id}>
                <button
                  onClick={() => navigate(`/chat/${match.id}`)}
                  className="w-full py-4 flex items-center gap-4 text-left hover:bg-muted/60 -mx-2 px-2 rounded-xl transition-colors"
                >
                  <UserAvatar name={other.name} photo={other.photos[0]} className="w-14 h-14 text-lg shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-baseline justify-between gap-3">
                      <p className="font-display text-lg leading-tight text-foreground truncate">{other.name || t("messages.unnamed")}</p>
                      <span className="text-[12px] text-muted-foreground shrink-0">
                        {fmtTime(match.last_message_at ?? match.created_at, locale)}
                      </span>
                    </div>
                    <p className={`text-sm truncate mt-0.5 ${match.last_message == null ? "text-secondary font-medium" : "text-muted-foreground"}`}>
                      {match.last_message == null
                        ? t("messages.firstMessage")
                        : match.last_message === REMOVED_CONTENT
                          ? t("chat.removed")
                          : match.last_message === UNREADABLE_CONTENT
                            ? t("chat.unreadable")
                            : match.last_message}
                    </p>
                    {match.listing_title && (
                      <p className="mt-1 text-[12px] text-muted-foreground truncate">{match.listing_title}</p>
                    )}
                  </div>
                </button>
              </li>
            );
          })}
        </ul>

        {!isLoading && matches.length === 0 && (
          <div className="py-16 space-y-3 animate-fade-in">
            <h2 className="text-[2rem] leading-tight text-foreground">{t("messages.emptyTitle")}</h2>
            <p className="text-muted-foreground leading-relaxed">{t("messages.emptyDesc")}</p>
          </div>
        )}
      </div>

      <AuthGate show={!isLoggedIn} onClose={() => {}} />
      <BottomNav />
    </div>
  );
};

export default Messages;
