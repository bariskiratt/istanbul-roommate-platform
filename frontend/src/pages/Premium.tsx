import { useNavigate } from "react-router-dom";
import { Zap, Star, Eye, MessageCircle, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import BottomNav from "@/components/layout/BottomNav";
import { toast } from "sonner";

const Premium = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background pb-20">
      <div className="sticky top-0 z-50 bg-card/95 backdrop-blur-lg border-b border-border px-6 py-4 flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="w-10 h-10 rounded-full bg-background flex items-center justify-center text-foreground hover:bg-muted transition-colors">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <h1 className="text-lg font-bold text-foreground">Premium</h1>
      </div>

      <div className="px-6 py-8 space-y-8">
        <div className="text-center space-y-3">
          <div className="w-16 h-16 rounded-3xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center mx-auto">
            <Zap className="w-8 h-8 text-primary-foreground" />
          </div>
          <h2 className="text-2xl font-extrabold text-foreground">RoomMatch Premium</h2>
          <p className="text-sm text-muted-foreground max-w-xs mx-auto">Daha fazla eşleşme, öne çıkan ilan ve sınırsız SuperMatch</p>
        </div>

        <div className="space-y-3">
          {[
            { icon: Star, title: "İlanını Öne Çıkar", desc: "İlanın Evler sayfasında en üstte görünsün" },
            { icon: Eye, title: "Sınırsız Görüntüleme", desc: "Seni kimlerin beğendiğini hemen gör" },
            { icon: Zap, title: "Sınırsız SuperMatch", desc: "Her gün sınırsız SuperMatch hakkı" },
            { icon: MessageCircle, title: "Öncelikli Mesajlaşma", desc: "Mesajların daha hızlı iletilsin" },
          ].map((f, i) => (
            <div key={i} className="card-listing p-5 flex items-center gap-4">
              <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center flex-shrink-0">
                <f.icon className="w-6 h-6 text-primary" />
              </div>
              <div>
                <p className="font-bold text-sm text-foreground">{f.title}</p>
                <p className="text-xs text-muted-foreground">{f.desc}</p>
              </div>
            </div>
          ))}
        </div>

        <Button
          onClick={() => toast("Ödeme sistemi yakında aktif olacak!")}
          className="w-full h-14 rounded-2xl bg-gradient-to-r from-primary to-secondary text-primary-foreground font-bold text-base shadow-lg"
        >
          <Zap className="w-5 h-5 mr-2" /> Aylık 99 ₺ — Premium'a Geç
        </Button>
      </div>

      <BottomNav />
    </div>
  );
};

export default Premium;
