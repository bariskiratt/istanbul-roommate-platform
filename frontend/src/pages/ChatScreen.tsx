import { useState, useRef, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Send, Home, MoreVertical, ArrowLeft } from "lucide-react";
import { mockMatches, mockMessages, currentUser } from "@/data/mockData";
import BottomNav from "@/components/layout/BottomNav";

const ChatScreen = () => {
  const { matchId } = useParams();
  const navigate = useNavigate();
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState(mockMessages.filter(m => m.matchId === (matchId || "match-1")));
  const bottomRef = useRef<HTMLDivElement>(null);

  const match = mockMatches.find(m => m.id === (matchId || "match-1"));
  const other = match?.userB;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = () => {
    if (!input.trim()) return;
    const newMsg = {
      id: `msg-${Date.now()}`,
      matchId: matchId || "match-1",
      senderId: currentUser.id,
      content: input,
      createdAt: new Date().toISOString(),
      isFlagged: false,
    };
    setMessages(prev => [...prev, newMsg]);
    setInput("");
  };

  if (!match || !other) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-muted-foreground">Eşleşme bulunamadı</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex flex-col pb-20">
      {/* Header — white bg, subtle shadow */}
      <div className="nav-header px-6 py-4 flex items-center gap-3 sticky top-0 z-50">
        <button
          onClick={() => navigate("/messages")}
          className="w-10 h-10 rounded-full bg-background flex items-center justify-center text-foreground hover:bg-muted transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <img src={other.photos[0]} alt="" className="w-10 h-10 rounded-full object-cover" />
        <div className="flex-1">
          <p className="font-bold text-sm text-foreground">{other.name}</p>
          <p className="text-[11px] text-muted-foreground">{other.university}</p>
        </div>
        <span className="text-[10px] px-2.5 py-1 rounded-full font-medium bg-lavender/50 text-foreground">
          {match.matchType === "ev_kisi" ? "🏠 Ev" : "👤 Kişi"}
        </span>
        <button className="w-10 h-10 rounded-full bg-background flex items-center justify-center text-muted-foreground hover:bg-muted transition-colors">
          <MoreVertical className="w-5 h-5" />
        </button>
      </div>

      {/* Listing link */}
      <div className="px-6 py-2">
        <div className="card-listing p-4 flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl bg-lavender/50 flex items-center justify-center">
            <Home className="w-5 h-5 text-primary" />
          </div>
          <div className="flex-1">
            <p className="text-xs font-semibold text-foreground">Eşleşme İlanı</p>
            <p className="text-[11px] text-muted-foreground truncate">
              {match.matchType === "ev_kisi" ? "Beşiktaş'ta Deniz Manzaralı 2+1" : "Kadıköy'de Ev Arkadaşı Arıyorum"}
            </p>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-3 space-y-3">
        {messages.map(msg => {
          const isMine = msg.senderId === currentUser.id;
          return (
            <div key={msg.id} className={`flex ${isMine ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[80%] ${isMine ? "message-sent" : "message-received"}`}>
                <p className="text-[15px] leading-relaxed">{msg.content}</p>
                <p className={`text-[10px] mt-1.5 ${isMine ? "text-primary-foreground/60" : "text-muted-foreground"}`}>
                  {new Date(msg.createdAt).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}
                </p>
              </div>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>

      {/* Input — large, rounded-full */}
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
          disabled={!input.trim()}
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
