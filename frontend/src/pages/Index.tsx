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
import { BRAND } from "@/lib/brand";
import { useI18n } from "@/i18n";
import ThemeToggle from "@/components/ThemeToggle";
import LanguageToggle from "@/components/LanguageToggle";

const quickDistricts = ["Kadıköy", "Beşiktaş", "Üsküdar", "Şişli", "Sarıyer", "Ataşehir"];

const median = (xs: number[]): number | null => {
  if (xs.length === 0) return null;
  const s = [...xs].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : Math.round((s[mid - 1] + s[mid]) / 2);
};

const Index = () => {
  const navigate = useNavigate();
  const { isLoggedIn, user, logout } = useAuth();
  const { t, n: fmtNum } = useI18n();
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
              {BRAND}
            </span>
          </Link>
          <div className="hidden md:flex items-center gap-8 text-sm font-medium text-muted-foreground">
            {isLoggedIn && user?.is_admin && (
              <button onClick={() => navigate("/listings")} className="hover:text-foreground transition-colors">{t("landing.findHouse")}</button>
            )}
            <button onClick={() => navigate("/swipe")} className="hover:text-foreground transition-colors">{t("landing.findRoommate")}</button>
            <button onClick={() => navigate("/explore")} className="hover:text-foreground transition-colors">{t("landing.budgetMap")}</button>
            <button onClick={() => navigate("/safety")} className="hover:text-foreground transition-colors">{t("landing.safety")}</button>
            <button onClick={() => document.getElementById("nasil-calisir")?.scrollIntoView({ behavior: "smooth" })} className="hover:text-foreground transition-colors">{t("landing.howItWorks")}</button>
          </div>
          <div className="flex items-center gap-2">
            <LanguageToggle />
            <ThemeToggle />
            {isLoggedIn ? (
              <>
                <button onClick={() => navigate("/profile")} className="w-9 h-9 rounded-full bg-primary/10 flex items-center justify-center hover:bg-primary/20 transition-colors">
                  <User className="w-4 h-4 text-primary" />
                </button>
                <Button variant="ghost" onClick={() => { logout(); }} className="text-sm font-medium hidden sm:inline-flex gap-1">
                  <LogOut className="w-4 h-4" /> {t("landing.logout")}
                </Button>
              </>
            ) : (
              <>
                <Button variant="ghost" onClick={() => navigate("/login")} className="text-sm font-medium hidden sm:inline-flex">{t("landing.login")}</Button>
                <Button onClick={() => navigate("/onboarding")} className="bg-primary text-primary-foreground rounded-full text-sm font-bold px-5">
                  {t("landing.getStarted")}
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
            {t("landing.heroLine1")}
            <br />
            <span className="italic text-secondary">{t("landing.heroFair")}</span> {t("landing.heroLine2")}
          </motion.h1>

          <motion.p
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.12, duration: 0.5 }}
            className="text-muted-foreground text-base md:text-lg max-w-xl mx-auto leading-relaxed"
          >
            {t("landing.heroSub")}
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
              {t(isLoggedIn ? "landing.ctaContinue" : "landing.ctaFree")}
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
            <Button
              variant="outline"
              onClick={() => navigate(user?.is_admin ? "/listings" : "/swipe")}
              className="rounded-full font-semibold px-8 py-3.5 text-base h-auto border-border"
            >
              {t("landing.ctaBrowse")}
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
              <span className="font-bold text-foreground text-lg tabular-nums">{listings.length > 0 ? fmtNum(listings.length) : "—"}</span>
              <span className="text-muted-foreground"> {t("landing.statListings")}</span>
            </div>
            <div>
              <span className="font-bold text-foreground text-lg tabular-nums">968</span>
              <span className="text-muted-foreground"> {t("landing.statNeighborhoods")}</span>
            </div>
            <div>
              <span className="font-bold text-foreground text-lg tabular-nums">{t("landing.statErrorValue")}</span>
              <span className="text-muted-foreground"> {t("landing.statError")}</span>
            </div>
          </motion.div>

          {/* Güven rozeti + hızlı semtler */}
          <div className="space-y-4 pt-2">
            <span className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full text-xs font-semibold bg-lavender/60 text-foreground">
              <ShieldCheck className="w-3.5 h-3.5" />
              {t("landing.eduBadge")}
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
                {t("landing.featuredTitle")}
                <ChevronRight className="w-6 h-6 text-muted-foreground group-hover:translate-x-1 transition-transform" />
              </h2>
              <p className="text-muted-foreground mt-1">{t("landing.featuredSub")}</p>
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
                      {t("common.houseListing")}
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
                        {l.rent != null ? `${fmtNum(l.rent)} ₺` : "—"}
                        <span className="font-normal text-muted-foreground text-xs">{t("common.roomShare")}</span>
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
              {t("landing.stepsEyebrow")}
            </p>
            <h2 className="text-3xl md:text-4xl font-semibold text-foreground">{t("landing.stepsTitle")}</h2>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              { n: "01", icon: User, title: t("landing.step1Title"), desc: t("landing.step1Desc") },
              { n: "02", icon: Layers, title: t("landing.step2Title"), desc: t("landing.step2Desc") },
              { n: "03", icon: Handshake, title: t("landing.step3Title"), desc: t("landing.step3Desc") },
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
              {t("landing.signupFree")} <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
            <p className="text-xs text-muted-foreground">{t("landing.signupNote")}</p>
          </motion.div>
        </div>
      </section>

      {/* ─── Semtler — gerçek verilerle ─── */}
      {districtStats.length > 0 && (
        <section className="max-w-7xl mx-auto px-6 py-16">
          <div className="text-center mb-10">
            <h2 className="text-2xl md:text-3xl font-semibold text-foreground">{t("landing.districtsTitle")}</h2>
            <p className="text-muted-foreground mt-1">{t("landing.districtsSub")}</p>
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
                <p className="text-xs text-muted-foreground mt-1.5">{t("landing.districtCount", { count: d.count })}</p>
                {d.median != null && (
                  <p className="text-xs font-semibold text-accent mt-0.5 tabular-nums">
                    {t("landing.districtMedian", { price: fmtNum(d.median) })}
                  </p>
                )}
              </motion.button>
            ))}
          </div>
        </section>
      )}

      {/* ─── Neden evdes.tr ─── */}
      <section className="max-w-5xl mx-auto px-6 py-16">
        <div className="grid md:grid-cols-3 gap-10">
          {[
            { icon: Sparkles, title: t("landing.why1Title"), desc: t("landing.why1Desc") },
            { icon: Shield, title: t("landing.why2Title"), desc: t("landing.why2Desc") },
            { icon: MapPin, title: t("landing.why3Title"), desc: t("landing.why3Desc") },
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
            <span className="font-bold text-foreground" style={{ fontFamily: "'Fraunces', Georgia, serif" }}>{BRAND}</span>
          </div>
          <div className="flex gap-6 text-sm text-muted-foreground">
            <button onClick={() => navigate("/safety")} className="hover:text-foreground transition-colors">{t("landing.safety")}</button>
            <button onClick={() => navigate("/explore")} className="hover:text-foreground transition-colors">{t("landing.budgetMap")}</button>
            <button onClick={() => navigate("/swipe")} className="hover:text-foreground transition-colors">{t("landing.footerListings")}</button>
            {/* Gerçek <a>: semt sayfaları SPA rotası değil, derleme anında
                üretilen statik HTML. Buradaki bağlantı arama motorunun ana
                sayfadan onlara ulaşmasını sağlar (iç bağlantı). */}
            <a href="/semt" className="hover:text-foreground transition-colors">{t("landing.districtPrices")}</a>
          </div>
          <p className="text-xs text-muted-foreground">© 2026 {BRAND}</p>
        </div>
      </footer>
    </div>
  );
};

export default Index;
