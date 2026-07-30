import { useState, useRef, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Send, Home, ArrowLeft } from "lucide-react";
import BottomNav from "@/components/layout/BottomNav";
import { useAuth } from "@/contexts/AuthContext";
import { fetchMatches, fetchMessages, sendMessage } from "@/lib/api";

const placeholderAvatar = "https://api.dicebear.com/9.x/thumbs/svg?seed=roommatch";

const ChatScreen = () => {
  const { matchId } = useParams();
  const navigate = useNavigate();
  const { user: me } = useAuth();
  const queryClient = useQueryClient();
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const id = Number(matchId);

  const { data: matches = [] } = useQuery({
    queryKey: ["matches"],
    queryFn: fetchMatches,
    enabled: me !== null,
  });
  const match = matches.find(m => m.id === id);

  // Basit gerçek zamanlılık: 4 sn'de bir yenile
  const { data: messages = [] } = useQuery({
    queryKey: ["messages", id],
    queryFn: () => fetchMessages(id),
    enabled: me !== null && Number.isFinite(id),
    refetchInterval: 4000,
  });

  const send = useMutation({
    mutationFn: (content: string) => sendMessage(id, content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["messages", id] });
      queryClient.invalidateQueries({ queryKey: ["matches"] });
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

  if (!me) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-muted-foreground">Mesajlaşmak için giriş yap</p>
      </div>
    );
  }

  if (matches.length > 0 && !match) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-muted-foreground">Eşleşme bulunamadı</p>
      </div>
    );
  }

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
        <div className="flex-1">
          <p className="font-bold text-sm text-foreground">{other?.name || "İsimsiz"}</p>
          <p className="text-[11px] text-muted-foreground">{other?.university ?? ""}</p>
        </div>
      </div>

      {/* Eşleşme ilanı */}
      {match?.listing_title && (
        <div className="px-6 py-2">
          <div className="card-listing p-4 flex items-center gap-3">
            <div className="w-11 h-11 rounded-2xl bg-lavender/50 flex items-center justify-center">
              <Home className="w-5 h-5 text-primary" />
            </div>
            <div className="flex-1">
              <p className="text-xs font-semibold text-foreground">Eşleşme İlanı</p>
              <p className="text-[11px] text-muted-foreground truncate">{match.listing_title}</p>
            </div>
          </div>
        </div>
      )}

      {/* Mesajlar */}
      <div className="flex-1 overflow-y-auto px-6 py-3 space-y-3">
        {messages.length === 0 && (
          <p className="text-center text-sm text-muted-foreground py-8">
            Henüz mesaj yok — ilk mesajı sen at! 👋
          </p>
        )}
        {messages.map(msg => {
          const isMine = msg.sender_id === me.id;
          return (
            <div key={msg.id} className={`flex ${isMine ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[80%] ${isMine ? "message-sent" : "message-received"}`}>
                <p className="text-[15px] leading-relaxed">{msg.content}</p>
                <p className={`text-[10px] mt-1.5 ${isMine ? "text-primary-foreground/60" : "text-muted-foreground"}`}>
                  {new Date(msg.created_at).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}
                </p>
              </div>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>

      {/* Giriş alanı */}
      <div className="sticky bottom-20 bg-card/80 backdrop-blur-lg px-6 py-3 flex items-center gap-3" style={{ boxShadow: '0 -1px 0 rgba(0,0,0,0.04)' }}>
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && handleSend()}
          placeholder="Bir mesaj yaz..."
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

      <BottomNav />
    </div>
  );
};

export default ChatScreen;
