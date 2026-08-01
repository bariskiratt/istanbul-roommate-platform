import { useState, useRef, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Send, Home, ArrowLeft, Flag } from "lucide-react";
import { toast } from "sonner";
import BottomNav from "@/components/layout/BottomNav";
import ReportDialog from "@/components/ReportDialog";
import { useAuth } from "@/contexts/AuthContext";
import {
  ApiError,
  REMOVED_CONTENT,
  UNREADABLE_CONTENT,
  fetchMatches,
  fetchMessages,
  sendMessage,
} from "@/lib/api";
import { parseUtc } from "@/lib/date";
import { useI18n } from "@/i18n";

const placeholderAvatar = "https://api.dicebear.com/9.x/thumbs/svg?seed=roommatch";

// UNREADABLE_CONTENT ("[unreadable]"): mesaj şifreli yazılmış ama sunucu onu
// çözememiş (backend/app/crypto.py).
// REMOVED_CONTENT ("[removed_by_moderation]"): yönetici mesajı kaldırmış
// (backend/app/moderation.py); satır sohbette kalır, metni geri gelmez.
// İkisi de dilden bağımsız işaret dizeleridir — birebir karşılaştırıp kendi
// çevirimizi basıyoruz, ham dize kullanıcıya asla gösterilmez.

const ChatScreen = () => {
  const { matchId } = useParams();
  const navigate = useNavigate();
  const { isLoggedIn, user: me } = useAuth();
  const { t, locale } = useI18n();
  const queryClient = useQueryClient();
  const [input, setInput] = useState("");
  const [reportOpen, setReportOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const id = Number(matchId);

  // isLoggedIn token'a bakar; `me` asenkron dolduğu için sayfa yenilemede
  // girişli kullanıcıya yanlışlıkla "giriş yap" ekranı göstermeyelim.
  const matchesQuery = useQuery({
    queryKey: ["matches"],
    queryFn: fetchMatches,
    enabled: isLoggedIn,
  });
  const matches = matchesQuery.data ?? [];
  const match = matches.find(m => m.id === id);

  // Basit gerçek zamanlılık: 4 sn'de bir yenile
  const messagesQuery = useQuery({
    queryKey: ["messages", id],
    queryFn: () => fetchMessages(id),
    enabled: isLoggedIn && Number.isFinite(id),
    refetchInterval: 4000,
    // 403/404 tekrar denemekle düzelmez; varsayılan 3 deneme "sohbet
    // bulunamadı" ekranını saniyelerce geciktirirdi. Ağ hatasında denenir.
    retry: (failureCount, error) =>
      !(error instanceof ApiError && error.status < 500) && failureCount < 3,
  });
  const messages = messagesQuery.data ?? [];

  const send = useMutation({
    mutationFn: (content: string) => sendMessage(id, content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["messages", id] });
      queryClient.invalidateQueries({ queryKey: ["matches"] });
    },
    // Sunucu gönderimi reddedebilir: karşı taraf askıdaysa 403, denetim metni
    // engellerse 422. Hata yutulduğu sürece kullanıcı yazdığı metni kaybediyor
    // ve mesajının neden gitmediğini hiç öğrenemiyordu.
    onError: (err, content) => {
      // Yeni bir şey yazmaya başlamadıysa reddedilen metni geri koy;
      // kullanıcı düzenleyip yeniden gönderebilsin.
      setInput(current => (current.trim() ? current : content));
      toast.error(t("chat.sendFailed"), {
        description: err instanceof Error ? err.message : t("common.error"),
      });
    },
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  const handleSend = () => {
    const content = input.trim();
    if (!content || send.isPending) return;
    setInput("");
    send.mutate(content);
  };

  if (!isLoggedIn) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-muted-foreground">{t("chat.loginRequired")}</p>
      </div>
    );
  }

  // Eşleşme kendi listemizde yok. Tek başına "sohbet bulunamadı" demek için
  // yeterli değil: karşı taraf askıya alındığında sunucu eşleşmeyi
  // /api/matches'ten eler ama GEÇMİŞİN OKUNMASINI ENGELLEMEZ
  // (backend/app/messages.py list_messages yalnızca tarafı olmayı arar).
  const missingFromList = matchesQuery.isSuccess && !match;

  // Mesajlar da alınamıyorsa (403 "tarafı değilsin" / 404 "eşleşme yok")
  // gerçekten erişimimiz yok; sunucunun açıklamasını olduğu gibi gösteririz.
  // Adres çubuğundaki id sayı bile değilse sorgu hiç çalışmaz — o durumu
  // ayrıca yakalarız, yoksa boş bir sohbet kabuğunda takılı kalırdık.
  if (!Number.isFinite(id) || (missingFromList && messagesQuery.isError)) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center px-6">
        <p className="text-muted-foreground text-center">
          {messagesQuery.error instanceof Error ? messagesQuery.error.message : t("chat.notFound")}
        </p>
      </div>
    );
  }

  // Geçmiş okunabiliyor ama sohbet kapalı: mesajlar gösterilir, gönderim
  // alanı yerine sebebi yazan bir kutu basılır.
  const closed = missingFromList;
  const other = match?.other_user;

  return (
    <div className="min-h-screen bg-background flex flex-col pb-20">
      {/* Header */}
      <div className="nav-header px-6 py-4 flex items-center gap-3 sticky top-0 z-50">
        <button
          onClick={() => navigate("/messages")}
          className="w-10 h-10 rounded-full bg-background flex items-center justify-center text-foreground hover:bg-muted transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <img
          src={other?.photos[0] ?? placeholderAvatar}
          alt=""
          className="w-10 h-10 rounded-full object-cover"
        />
        <div className="flex-1 min-w-0">
          {/* Sohbet kapalıysa eşleşme kaydı elimizde yok: karşı tarafın adını
              bilmiyoruz. "İsimsiz" yazmak profili hakkında yanlış bir şey
              söylerdi; onun yerine sohbetin durumunu yazıyoruz. */}
          <p className="font-bold text-sm text-foreground truncate">
            {other ? other.name || t("messages.unnamed") : closed ? t("chat.closedTitle") : ""}
          </p>
          <p className="text-[11px] text-muted-foreground">{other?.university ?? ""}</p>
        </div>
        {/* Karşı kullanıcıyı bildir; eşleşme yüklenmeden hedef id bilinmez */}
        {other && (
          <button
            onClick={() => setReportOpen(true)}
            aria-label={t("report.reportUser")}
            title={t("report.reportUser")}
            className="w-10 h-10 rounded-full bg-background flex items-center justify-center text-muted-foreground hover:bg-muted hover:text-destructive transition-colors shrink-0"
          >
            <Flag className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Eşleşme ilanı */}
      {match?.listing_title && (
        <div className="px-6 py-2">
          <div className="card-listing p-4 flex items-center gap-3">
            <div className="w-11 h-11 rounded-2xl bg-lavender/50 flex items-center justify-center">
              <Home className="w-5 h-5 text-primary" />
            </div>
            <div className="flex-1">
              <p className="text-xs font-semibold text-foreground">{t("chat.matchListing")}</p>
              <p className="text-[11px] text-muted-foreground truncate">{match.listing_title}</p>
            </div>
          </div>
        </div>
      )}

      {/* Mesajlar */}
      <div className="flex-1 overflow-y-auto px-6 py-3 space-y-3">
        {messagesQuery.isError ? (
          <p className="text-center text-sm text-destructive py-8">{t("chat.loadFailed")}</p>
        ) : (
          messagesQuery.isSuccess &&
          messages.length === 0 && (
            <p className="text-center text-sm text-muted-foreground py-8">{t("chat.empty")}</p>
          )
        )}
        {messages.map(msg => {
          const isMine = me !== null && msg.sender_id === me.id;
          const unreadable = msg.content === UNREADABLE_CONTENT;
          const removed = msg.content === REMOVED_CONTENT;
          const placeholder = unreadable || removed;
          return (
            <div key={msg.id} className={`flex ${isMine ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[80%] ${isMine ? "message-sent" : "message-received"}`}>
                <p className={`text-[15px] leading-relaxed${placeholder ? " italic opacity-70" : ""}`}>
                  {removed ? t("chat.removed") : unreadable ? t("chat.unreadable") : msg.content}
                </p>
                <p className={`text-[10px] mt-1.5 ${isMine ? "text-primary-foreground/60" : "text-muted-foreground"}`}>
                  {parseUtc(msg.created_at).toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" })}
                </p>
              </div>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>

      {/* Giriş alanı — sohbet kapalıysa yerine sebebi yazan kutu gelir.
          Kutuyu göstermek, gönderilemeyeceği belli olan bir alanı canlı
          bırakıp 403'ü kullanıcının yüzüne çarpmaktan dürüst. */}
      {closed ? (
        <div className="sticky bottom-20 bg-card/80 backdrop-blur-lg px-6 py-3" style={{ boxShadow: '0 -1px 0 rgba(0,0,0,0.04)' }}>
          <p className="text-xs font-semibold text-foreground">{t("chat.closedTitle")}</p>
          <p className="text-[11px] text-muted-foreground mt-0.5">{t("chat.closedDesc")}</p>
        </div>
      ) : (
      <div className="sticky bottom-20 bg-card/80 backdrop-blur-lg px-6 py-3 flex items-center gap-3" style={{ boxShadow: '0 -1px 0 rgba(0,0,0,0.04)' }}>
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && handleSend()}
          placeholder={t("chat.placeholder")}
          className="flex-1 h-12 bg-background rounded-full px-5 text-[15px] text-foreground placeholder:text-muted-foreground outline-none focus:ring-2 focus:ring-primary/20 transition-shadow"
          style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.04)' }}
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || send.isPending}
          className="w-11 h-11 rounded-full bg-primary text-primary-foreground flex items-center justify-center disabled:opacity-40 hover:opacity-90 transition-opacity active:scale-95 shadow-md"
        >
          <Send className="w-5 h-5" />
        </button>
      </div>
      )}

      {other && (
        <ReportDialog
          open={reportOpen}
          onClose={() => setReportOpen(false)}
          targetType="user"
          targetId={other.id}
          targetLabel={other.name || t("messages.unnamed")}
        />
      )}

      <BottomNav />
    </div>
  );
};

export default ChatScreen;
