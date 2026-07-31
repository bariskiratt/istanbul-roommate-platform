import { useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import {
  Home, Shield, Sparkles, ChevronLeft, ChevronRight, MapPin, BedDouble,
  ShieldCheck, User, Layers, Handshake, LogOut, ArrowRight,
} from "lucide-react";
import { motion } from "framer-motion";
import { useMemo, useRef } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { fetchListings } from "@/lib/api";

const quickDistricts = ["Kadıköy", "Beşiktaş", "Üsküdar", "Şişli", "Sarıyer", "Ataşehir"];

const fmt = new Intl.NumberFormat("tr-TR");

const median = (xs: number[]): number | null => {
  if (xs.length === 0) return null;
  const s = [...xs].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : Math.round((s[mid - 1] + s[mid]) / 2);
};

const Index = () => {
  const navigate = useNavigate();
  const { isLoggedIn, user, logout } = useAuth();
  const listingsRef = useRef<HTMLDivElement>(null);

  // Vitrindeki her şey gerçek: canlı ilanlardan beslenir
  const { data: listings = [] } = useQuery({
    queryKey: ["listings"],
    queryFn: () => fetchListings(),
    staleTime: 60_000,
  });
  const houses = listings.filter(l => l.type === "ev_ilani").slice(0, 10);

  // Semt kartları: fotoğraf yerine gerçek veri — ilan sayısı ve medyan oda payı
  const districtStats = useMemo(() => {
    const acc = new Map<string, { count: number; rents: number[] }>();
    for (const l of listings) {
      const s = acc.get(l.district) ?? { count: 0, rents: [] };
      s.count += 1;
      if (l.type === "ev_ilani" && l.rent != null) s.rents.push(l.rent);
      acc.set(l.district, s);
    }
    return [...acc.entries()]
      .map(([name, s]) => ({ name, count: s.count, median: median(s.rents) }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);
  }, [listings]);

  const scroll = (ref: React.RefObject<HTMLDivElement>, dir: "left" | "right") => {
    ref.current?.scrollBy({ left: dir === "left" ? -320 : 320, behavior: "smooth" });
  };

  return (
    <div className="min-h-screen bg-background">
      {/* ─── NAVBAR ─── */}
      <nav className="sticky top-0 z-50 bg-background/90 backdrop-blur-lg border-b border-border">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5 cursor-pointer">
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
              <Home className="w-4 h-4 text-primary-foreground" />
            </div>
            <span className="font-bold text-xl text-foreground tracking-tight" style={{ fontFamily: "'Fraunces', Georgia, serif" }}>
              RoomMatch
            </span>
          </Link>
          <div className="hidden md:flex items-center gap-8 text-sm font-medium text-muted-foreground">
            {isLoggedIn && user?.is_admin && (
              <button onClick={() => navigate("/listings")} className="hover:text-foreground transition-colors">Ev Bul</button>
            )}
            <button onClick={() => navigate("/swipe")} className="hover:text-foreground transition-colors">Ev Arkadaşı Bul</button>
            <button onClick={() => navigate("/explore")} className="hover:text-foreground transition-colors">Bütçe Haritası</button>
            <button onClick={() => navigate("/safety")} className="hover:text-foreground transition-colors">Güvenlik</button>
            <button onClick={() => document.getElementById("nasil-calisir")?.scrollIntoView({ behavior: "smooth" })} className="hover:text-foreground transition-colors">Nasıl Çalışır?</button>
          </div>
          <div className="flex items-center gap-3">
            {isLoggedIn ? (
              <>
                <button onClick={() => navigate("/profile")} className="w-9 h-9 rounded-full bg-primary/10 flex items-center justify-center hover:bg-primary/20 transition-colors">
                  <User className="w-4 h-4 text-primary" />
                </button>
                <Button variant="ghost" onClick={() => { logout(); }} className="text-sm font-medium hidden sm:inline-flex gap-1">
                  <LogOut className="w-4 h-4" /> Çıkış Yap
                </Button>
              </>
            ) : (
              <>
                <Button variant="ghost" onClick={() => navigate("/login")} className="text-sm font-medium hidden sm:inline-flex">Giriş Yap</Button>
                <Button onClick={() => navigate("/onboarding")} className="bg-primary text-primary-foreground rounded-full text-sm font-bold px-5">
                  Hemen Başla
                </Button>
              </>
            )}
          </div>
        </div>
      </nav>

      {/* ─── HERO — editoryal, sakin ─── */}
      <section className="relative overflow-hidden border-b border-border">
        {/* Harita dokusu: tema rengine boyanmış, çok silik */}
        <div className="absolute inset-0 opacity-[0.07] pointer-events-none">
          <img src="/images/istanbul-map.png" alt="" className="w-full h-full object-cover" />
        </div>

        <div className="relative z-10 max-w-5xl mx-auto px-6 py-24 md:py-32 text-center space-y-8">
          <motion.h1
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.5 }}
            className="text-4xl md:text-6xl font-semibold text-foreground leading-[1.1]"
          >
            Doğru ev arkadaşı,
            <br />
            <span className="italic text-secondary">adil</span> bir kirayla.
          </motion.h1>

          <motion.p
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.12, duration: 0.5 }}
            className="text-muted-foreground text-base md:text-lg max-w-xl mx-auto leading-relaxed"
          >
            İstanbul'daki üniversite öğrencileri için eşleşme platformu. Makine
            öğrenmesi destekli kira danışmanı, mahalle bütçe haritası ve
            doğrulanmış öğrenci topluluğu.
          </motion.p>

          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.22, duration: 0.5 }}
            className="flex flex-wrap items-center justify-center gap-3"
          >
            <Button
              onClick={() => navigate(isLoggedIn ? "/swipe" : "/onboarding")}
              className="rounded-full bg-primary text-primary-foreground font-bold px-8 py-3.5 text-base h-auto"
            >
              {isLoggedIn ? "Keşfetmeye Devam Et" : "Ücretsiz Başla"}
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
            <Button
              variant="outline"
              onClick={() => navigate(user?.is_admin ? "/listings" : "/swipe")}
              className="rounded-full font-semibold px-8 py-3.5 text-base h-auto border-border"
            >
              İlanlara Göz At
            </Button>
          </motion.div>

          {/* Gerçek sayılar */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.35, duration: 0.6 }}
            className="flex flex-wrap justify-center gap-x-10 gap-y-3 pt-4 text-sm"
          >
            <div>
              <span className="font-bold text-foreground text-lg tabular-nums">{listings.length > 0 ? fmt.format(listings.length) : "—"}</span>
              <span className="text-muted-foreground"> aktif ilan</span>
            </div>
            <div>
              <span className="font-bold text-foreground text-lg tabular-nums">968</span>
              <span className="text-muted-foreground"> mahalle haritada</span>
            </div>
            <div>
              <span className="font-bold text-foreground text-lg tabular-nums">%15,1</span>
              <span className="text-muted-foreground"> medyan model hatası</span>
            </div>
          </motion.div>

          {/* Güven rozeti + hızlı semtler */}
          <div className="space-y-4 pt-2">
            <span className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full text-xs font-semibold bg-lavender/60 text-foreground">
              <ShieldCheck className="w-3.5 h-3.5" />
              Sadece .edu.tr uzantılı üniversite e-postasıyla kayıt
            </span>
            <div className="flex flex-wrap justify-center gap-2">
              {quickDistricts.map(d => (
                <button
                  key={d}
                  onClick={() => navigate("/listings")}
                  className="px-4 py-1.5 rounded-full text-xs font-medium bg-card border border-border text-muted-foreground hover:text-foreground hover:border-primary/40 transition-colors"
                >
                  {d}
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ─── Öne çıkan evler — gerçek ilanlar ─── */}
      {houses.length > 0 && (
        <section className="max-w-7xl mx-auto px-6 py-16">
          <div className="flex items-end justify-between mb-8">
            <button onClick={() => navigate(user?.is_admin ? "/listings" : "/swipe")} className="group text-left">
              <h2 className="text-2xl md:text-3xl font-semibold text-foreground inline-flex items-center gap-2">
                Öne çıkan evler
                <ChevronRight className="w-6 h-6 text-muted-foreground group-hover:translate-x-1 transition-transform" />
              </h2>
              <p className="text-muted-foreground mt-1">Oda payı fiyatlarıyla</p>
            </button>
            <div className="flex gap-2">
              <button onClick={() => scroll(listingsRef, "left")} className="w-9 h-9 rounded-full border border-border bg-card flex items-center justify-center hover:bg-muted transition-colors">
                <ChevronLeft className="w-4 h-4 text-foreground" />
              </button>
              <button onClick={() => scroll(listingsRef, "right")} className="w-9 h-9 rounded-full border border-border bg-card flex items-center justify-center hover:bg-muted transition-colors">
                <ChevronRight className="w-4 h-4 text-foreground" />
              </button>
            </div>
          </div>
          <div ref={listingsRef} className="flex gap-5 overflow-x-auto scrollbar-hide pb-4 -mx-2 px-2 snap-x">
            {houses.map((l, i) => (
              <motion.div
                key={l.id}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: Math.min(i * 0.05, 0.3) }}
                className="flex-shrink-0 w-72 snap-start"
              >
                <div onClick={() => navigate(user?.is_admin ? "/listings" : "/swipe")} className="card-listing overflow-hidden group cursor-pointer h-full">
                  <div className="relative aspect-[4/3] overflow-hidden bg-muted">
                    {l.photos[0] ? (
                      <img src={l.photos[0]} alt={l.title} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <Home className="w-10 h-10 text-muted-foreground" />
                      </div>
                    )}
                    <span className="absolute top-3 left-3 bg-secondary/90 text-secondary-foreground text-[10px] font-semibold px-2.5 py-1 rounded-full backdrop-blur-sm">
                      Ev İlanı
                    </span>
                  </div>
                  <div className="p-4 space-y-1.5">
                    <h3 className="font-bold text-foreground text-sm line-clamp-1">{l.title}</h3>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <MapPin className="w-3 h-3" /> {l.district}
                      {l.room_count && (
                        <>
                          <span>·</span>
                          <BedDouble className="w-3 h-3" /> {l.room_count}
                        </>
                      )}
                    </div>
                    <div className="pt-1">
                      <span className="font-bold text-foreground">
                        {l.rent != null ? `${fmt.format(l.rent)} ₺` : "—"}
                        <span className="font-normal text-muted-foreground text-xs">/ay oda payı</span>
                      </span>
                    </div>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </section>
      )}

      {/* ─── Nasıl Çalışır? ─── */}
      <section id="nasil-calisir" className="py-20 px-6 bg-card border-y border-border">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <p className="text-xs font-bold tracking-[0.25em] uppercase mb-3 text-secondary">
              3 adımda ev arkadaşı bul
            </p>
            <h2 className="text-3xl md:text-4xl font-semibold text-foreground">Bu kadar basit.</h2>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              {
                n: "01", icon: User, title: "Profilini oluştur",
                desc: "Üniversite e-postanla kayıt ol. Bütçeni, yaşam tarzını ve tercih ettiğin semtleri belirt.",
              },
              {
                n: "02", icon: Layers, title: "Keşfet ve kaydır",
                desc: "Gerçek ilanları gör, beğendiklerine sağa kaydır. Adil fiyat danışmanı kiraların piyasaya uygunluğunu söyler.",
              },
              {
                n: "03", icon: Handshake, title: "Eşleş ve tanış",
                desc: "Karşılıklı beğeni eşleşme yaratır. Uygulama içi mesajlaşmayla güvenle iletişime geç.",
              },
            ].map((step, i) => (
              <motion.div
                key={step.n}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.12 }}
                className="relative bg-background border border-border rounded-2xl p-8 hover:shadow-lg transition-shadow duration-300"
              >
                <span className="absolute -top-4 -left-2 text-7xl font-extrabold text-muted-foreground/10 select-none" style={{ fontFamily: "'Fraunces', Georgia, serif" }}>
                  {step.n}
                </span>
                <div className="w-14 h-14 rounded-2xl bg-secondary flex items-center justify-center mb-5">
                  <step.icon className="w-6 h-6 text-secondary-foreground" />
                </div>
                <h3 className="text-lg font-bold text-foreground mb-2">{step.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{step.desc}</p>
              </motion.div>
            ))}
          </div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.3, duration: 0.5 }}
            className="text-center mt-16 space-y-4"
          >
            <Button
              onClick={() => navigate("/onboarding")}
              className="rounded-full bg-primary text-primary-foreground font-bold px-8 py-4 text-base h-auto"
            >
              Ücretsiz Kaydol <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
            <p className="text-xs text-muted-foreground">
              Kredi kartı gerekmez · Tamamen ücretsiz · .edu.tr gerekli
            </p>
          </motion.div>
        </div>
      </section>

      {/* ─── Semtler — gerçek verilerle ─── */}
      {districtStats.length > 0 && (
        <section className="max-w-7xl mx-auto px-6 py-16">
          <div className="text-center mb-10">
            <h2 className="text-2xl md:text-3xl font-semibold text-foreground">İstanbul'da ev ara</h2>
            <p className="text-muted-foreground mt-1">En çok ilan olan semtler ve medyan oda payları</p>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-4">
            {districtStats.map((d, i) => (
              <motion.button
                key={d.name}
                initial={{ opacity: 0, scale: 0.95 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true }}
                transition={{ delay: Math.min(i * 0.03, 0.2) }}
                onClick={() => navigate(user?.is_admin ? "/listings" : "/swipe")}
                className="card-listing p-5 text-left hover:shadow-lg transition-shadow group"
              >
                <p className="text-lg font-bold text-foreground group-hover:text-secondary transition-colors" style={{ fontFamily: "'Fraunces', Georgia, serif" }}>
                  {d.name}
                </p>
                <p className="text-xs text-muted-foreground mt-1.5">{d.count} ilan</p>
                {d.median != null && (
                  <p className="text-xs font-semibold text-accent mt-0.5 tabular-nums">
                    ~{fmt.format(d.median)} ₺/ay oda
                  </p>
                )}
              </motion.button>
            ))}
          </div>
        </section>
      )}

      {/* ─── Neden RoomMatch ─── */}
      <section className="max-w-5xl mx-auto px-6 py-16">
        <div className="grid md:grid-cols-3 gap-10">
          {[
            { icon: Sparkles, title: "Adil fiyat danışmanı", desc: "LightGBM modeli, istenen kiranın piyasaya uygunluğunu mahalle bazında söyler — TÜFE ile bugüne endeksli." },
            { icon: Shield, title: ".edu.tr ile güvende", desc: "Sadece doğrulanmış üniversite öğrencileri. Sahte profil yok." },
            { icon: MapPin, title: "Bütçe haritası", desc: "968 mahalle bütçene göre yeşil/sarı/kırmızı renklenir — hangi semtin bütçene uyduğunu tek bakışta gör." },
          ].map((f, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
              className="text-center space-y-4"
            >
              <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto">
                <f.icon className="w-7 h-7 text-primary" />
              </div>
              <h3 className="text-lg font-bold text-foreground">{f.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ─── FOOTER ─── */}
      <footer className="bg-background border-t border-border">
        <div className="max-w-7xl mx-auto px-6 py-10 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-primary flex items-center justify-center">
              <Home className="w-3.5 h-3.5 text-primary-foreground" />
            </div>
            <span className="font-bold text-foreground" style={{ fontFamily: "'Fraunces', Georgia, serif" }}>RoomMatch</span>
          </div>
          <div className="flex gap-6 text-sm text-muted-foreground">
            <button onClick={() => navigate("/safety")} className="hover:text-foreground transition-colors">Güvenlik</button>
            <button onClick={() => navigate("/explore")} className="hover:text-foreground transition-colors">Bütçe Haritası</button>
            <button onClick={() => navigate("/swipe")} className="hover:text-foreground transition-colors">İlanlar</button>
          </div>
          <p className="text-xs text-muted-foreground">© 2026 RoomMatch</p>
        </div>
      </footer>
    </div>
  );
};

export default Index;
