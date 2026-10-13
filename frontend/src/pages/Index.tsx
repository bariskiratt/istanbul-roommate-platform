import { useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight, MapPin, User, LogOut } from "lucide-react";
import { useMemo, useRef } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { fetchListings } from "@/lib/api";
import { BRAND } from "@/lib/brand";
import { useI18n } from "@/i18n";
import ThemeToggle from "@/components/ThemeToggle";
import LanguageToggle from "@/components/LanguageToggle";
import Wordmark from "@/components/campus/Wordmark";
import StudentCard from "@/components/campus/StudentCard";
import PriceRuler from "@/components/campus/PriceRuler";
import MapSketch from "@/components/campus/MapSketch";

const median = (xs: number[]): number | null => {
  if (xs.length === 0) return null;
  const s = [...xs].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : Math.round((s[mid - 1] + s[mid]) / 2);
};

// "Kira adil mi?" kartındaki cetvelin örnek değerleri. Gerçek bir ilan
// değil; kartın üstünde "Örnek" yazar. Gerçek hesap ilan kartında görünür.
const EXAMPLE = { low: 9800, mid: 11200, high: 12600, asking: 14000 };

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

  // Semt tablosu: medyan oda payı, gerçek ilanlardan. Sıralama ilan sayısına
  // göre ama sayının kendisi bilerek gösterilmiyor: yayının ilk günlerinde
  // 1, 2 gibi sayılar siteyi boş gösteriyordu (ana başlıktaki sayı gibi).
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

  const browsePath = user?.is_admin ? "/listings" : "/swipe";

  const scroll = (dir: "left" | "right") => {
    listingsRef.current?.scrollBy({ left: dir === "left" ? -320 : 320, behavior: "smooth" });
  };


  return (
    <div className="min-h-screen bg-background">
      {/* ─── Üst çubuk ─── */}
      {/* Gezinme öğeleri düğme değil <Link> (gerçek <a href>): Google yalnızca
          href'i olan bağlantıyı izler. onClick'li düğmeler yüzünden ana
          sayfadan /explore, /safety ve /privacy'ye hiçbir yol görünmüyordu. */}
      <nav className="sticky top-0 z-50 bg-background/90 backdrop-blur-md border-b border-border">
        <div className="max-w-6xl mx-auto px-5 md:px-8 h-16 flex items-center justify-between gap-4">
          <Link to="/" aria-label={BRAND}>
            <Wordmark />
          </Link>
          <div className="hidden lg:flex items-center gap-7 text-[15px] text-muted-foreground">
            {isLoggedIn && user?.is_admin && (
              <Link to="/listings" className="hover:text-foreground transition-colors">{t("landing.findHouse")}</Link>
            )}
            <Link to="/swipe" className="hover:text-foreground transition-colors">{t("landing.findRoommate")}</Link>
            <Link to="/explore" className="hover:text-foreground transition-colors">{t("landing.budgetMap")}</Link>
            <Link to="/safety" className="hover:text-foreground transition-colors">{t("landing.safety")}</Link>
            <button onClick={() => document.getElementById("nasil-calisir")?.scrollIntoView({ behavior: "smooth" })} className="hover:text-foreground transition-colors">{t("landing.howItWorks")}</button>
          </div>
          <div className="flex items-center gap-1">
            <LanguageToggle />
            <ThemeToggle />
            {isLoggedIn ? (
              <>
                <button
                  onClick={() => navigate("/profile")}
                  aria-label={t("nav.profile")}
                  className="w-9 h-9 rounded-full flex items-center justify-center hover:bg-muted transition-colors"
                >
                  <User className="w-4 h-4" />
                </button>
                <Button variant="ghost" onClick={() => { logout(); }} className="hidden sm:inline-flex">
                  <LogOut /> {t("landing.logout")}
                </Button>
              </>
            ) : (
              <>
                <Button asChild variant="ghost" className="hidden sm:inline-flex">
                  <Link to="/login">{t("landing.login")}</Link>
                </Button>
                <Button asChild className="ml-1 px-5">
                  <Link to="/onboarding">{t("landing.getStarted")}</Link>
                </Button>
              </>
            )}
          </div>
        </div>
      </nav>

      {/* ─── Giriş: başlık solda, boş öğrenci kartı sağda ─── */}
      <header className="max-w-6xl mx-auto px-5 md:px-8 pt-14 pb-16 md:pt-24 md:pb-24 grid lg:grid-cols-12 gap-14 lg:gap-10 items-center">
        <div className="lg:col-span-7">
          <h1 className="text-[2.75rem] leading-[1.02] sm:text-6xl lg:text-[4.6rem] font-medium tracking-[-0.025em] text-foreground max-w-[14ch]">
            {t("landing.heroTitle")}
          </h1>
          <p className="mt-6 text-lg md:text-[1.2rem] leading-relaxed text-muted-foreground max-w-[34rem]">
            {t("landing.heroSub")}
          </p>
          <div className="mt-9 flex flex-wrap items-center gap-3">
            <Button asChild size="lg" className="h-12 px-7 text-base">
              <Link to={isLoggedIn ? "/swipe" : "/onboarding"}>
                {t(isLoggedIn ? "landing.ctaContinue" : "landing.ctaFree")}
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline" className="h-12 px-7 text-base">
              <Link to={browsePath}>{t("landing.ctaBrowse")}</Link>
            </Button>
          </div>
          {/* İlan sayısı bilerek yok: yayının ilk günlerinde küçük bir sayı
              siteyi boş gösteriyordu. */}
          <p className="mt-8 text-sm text-muted-foreground">
            <span className="font-semibold text-foreground">968</span> {t("landing.statNeighborhoods")}
            <span className="mx-3 text-border" aria-hidden="true">|</span>
            <span className="font-semibold text-foreground">{t("landing.statErrorValue")}</span> {t("landing.statError")}
          </p>
        </div>

        <div className="lg:col-span-5 relative max-w-[440px] w-full mx-auto lg:mx-0 lg:ml-auto">
          <StudentCard name="" blank verified animateStamp className="lg:rotate-[1.5deg]" />
          {/* Kenar notu: kartın altına kalemle yazılmış gibi */}
          <div className="mt-5 flex items-start gap-2 text-secondary pl-3">
            <svg width="38" height="30" viewBox="0 0 38 30" fill="none" aria-hidden="true" className="shrink-0 -mt-3">
              <path d="M3 27C10 22 20 14 31 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              <path d="M23 5.5L31.5 5L29.5 13" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <p className="font-hand text-[1.3rem] leading-tight">{t("landing.cardNote")}</p>
          </div>
        </div>
      </header>

      {/* ─── Öne çıkan evler — gerçek ilanlar ─── */}
      {houses.length > 0 && (
        <section className="border-t border-border">
          <div className="max-w-6xl mx-auto px-5 md:px-8 py-16">
            <div className="flex items-end justify-between gap-4 mb-7">
              <div>
                <h2 className="text-3xl md:text-4xl text-foreground">{t("landing.featuredTitle")}</h2>
                <p className="text-muted-foreground mt-1.5">{t("landing.featuredSub")}</p>
              </div>
              <div className="hidden sm:flex gap-2">
                <button onClick={() => scroll("left")} aria-label={t("common.back")} className="w-10 h-10 rounded-full border border-border flex items-center justify-center hover:bg-muted transition-colors">
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <button onClick={() => scroll("right")} aria-label={t("landing.more")} className="w-10 h-10 rounded-full border border-border flex items-center justify-center hover:bg-muted transition-colors">
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
            <div ref={listingsRef} className="flex gap-5 overflow-x-auto scrollbar-hide pb-2 -mx-5 px-5 md:mx-0 md:px-0 snap-x">
              {houses.map(l => (
                <button
                  key={l.id}
                  onClick={() => navigate(browsePath)}
                  className="flex-shrink-0 w-[260px] snap-start text-left group"
                >
                  <div className="aspect-[4/5] rounded-2xl overflow-hidden bg-muted">
                    {l.photos[0] && (
                      <img src={l.photos[0]} alt="" className="w-full h-full object-cover group-hover:scale-[1.03] transition-transform duration-500" />
                    )}
                  </div>
                  <h3 className="mt-3 font-display text-lg leading-snug text-foreground line-clamp-2">{l.title}</h3>
                  <p className="mt-1 text-sm text-muted-foreground flex items-center gap-1">
                    <MapPin className="w-3.5 h-3.5" /> {l.district}
                    {l.room_count && <span className="ml-2">{l.room_count}</span>}
                  </p>
                  {l.rent != null && (
                    <p className="mt-1.5 text-[15px]">
                      <span className="marker font-semibold">{fmtNum(l.rent)} TL</span>
                      <span className="text-muted-foreground text-sm">{t("common.roomShare")}</span>
                    </p>
                  )}
                </button>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* ─── Nasıl çalışır: gerçek bir sıra, numaralar bu yüzden var ─── */}
      <section id="nasil-calisir" className="border-t border-border bg-muted/50">
        <div className="max-w-6xl mx-auto px-5 md:px-8 py-16 md:py-20 grid lg:grid-cols-12 gap-10">
          <div className="lg:col-span-4">
            <h2 className="text-3xl md:text-4xl text-foreground">{t("landing.howItWorks")}</h2>
            <p className="mt-3 text-muted-foreground max-w-xs">{t("landing.stepsSub")}</p>
          </div>
          <ol className="lg:col-span-8 divide-y divide-border border-y border-border">
            {[
              { title: t("landing.step1Title"), desc: t("landing.step1Desc") },
              { title: t("landing.step2Title"), desc: t("landing.step2Desc") },
              { title: t("landing.step3Title"), desc: t("landing.step3Desc") },
            ].map((step, i) => (
              <li key={step.title} className="grid grid-cols-[3rem_1fr] gap-4 py-6">
                <span className="font-display text-4xl leading-none text-secondary tabular-nums">{i + 1}</span>
                <div>
                  <h3 className="text-xl text-foreground">{step.title}</h3>
                  <p className="mt-1.5 text-muted-foreground leading-relaxed max-w-[52ch]">{step.desc}</p>
                </div>
              </li>
            ))}
          </ol>
          <div className="lg:col-start-5 lg:col-span-8 flex flex-wrap items-center gap-x-5 gap-y-3">
            <Button asChild size="lg" className="h-12 px-7 text-base">
              <Link to="/onboarding">{t("landing.signupFree")}</Link>
            </Button>
            <p className="text-sm text-muted-foreground">{t("landing.signupNote")}</p>
          </div>
        </div>
      </section>

      {/* ─── Neden: Hinge'in soru-cevap kartları gibi; her cevabın kendi malzemesi var ─── */}
      <section className="max-w-6xl mx-auto px-5 md:px-8 py-16 md:py-20">
        <h2 className="text-3xl md:text-4xl text-foreground mb-8">{t("landing.whyTitle")}</h2>
        <div className="space-y-5">
          {/* Kira adil mi? — kareli kâğıt, çünkü cevabı model hesaplıyor */}
          <article className="rounded-2xl border border-border grid md:grid-cols-2 overflow-hidden">
            <div className="p-6 md:p-8">
              <p className="text-[15px] font-semibold text-foreground">{t("landing.why1Prompt")}</p>
              <p className="mt-3 font-display text-2xl md:text-[1.75rem] leading-snug text-foreground">{t("landing.why1Answer")}</p>
            </div>
            <div className="paper-grid border-t md:border-t-0 md:border-l border-border p-6 md:p-8 flex flex-col justify-center">
              <p className="text-[12px] text-muted-foreground mb-3">{t("landing.exampleLabel")}</p>
              <PriceRuler low={EXAMPLE.low} mid={EXAMPLE.mid} high={EXAMPLE.high} asking={EXAMPLE.asking} />
              <p className="mt-3 text-sm text-foreground">
                {t("landing.exampleCaption", { asking: fmtNum(EXAMPLE.asking), low: fmtNum(EXAMPLE.low), high: fmtNum(EXAMPLE.high) })}
              </p>
            </div>
          </article>

          {/* Karşımdaki gerçekten öğrenci mi? — mühür */}
          <article className="rounded-2xl border border-border grid md:grid-cols-2 overflow-hidden">
            <div className="p-6 md:p-8">
              <p className="text-[15px] font-semibold text-foreground">{t("landing.why2Prompt")}</p>
              <p className="mt-3 font-display text-2xl md:text-[1.75rem] leading-snug text-foreground">{t("landing.why2Answer")}</p>
            </div>
            <div className="border-t md:border-t-0 md:border-l border-border p-8 flex items-center justify-center bg-muted/40">
              <span className="stamp -rotate-[7deg] text-base px-4 py-2">
                <span className="text-2xl">{t("card.stampTop")}</span>
                <span className="font-semibold normal-case tracking-normal">{t("card.stampBottom")}</span>
              </span>
            </div>
          </article>

          {/* Bütçem hangi semte yeter? — harita */}
          <article className="rounded-2xl border border-border grid md:grid-cols-2 overflow-hidden">
            <div className="p-6 md:p-8">
              <p className="text-[15px] font-semibold text-foreground">{t("landing.why3Prompt")}</p>
              <p className="mt-3 font-display text-2xl md:text-[1.75rem] leading-snug text-foreground">{t("landing.why3Answer")}</p>
              <Button asChild variant="outline" className="mt-6">
                <Link to="/explore">{t("landing.mapCta")}</Link>
              </Button>
            </div>
            <Link
              to="/explore"
              aria-label={t("landing.mapCta")}
              className="relative min-h-[260px] border-t md:border-t-0 md:border-l border-border overflow-hidden bg-muted/40"
            >
              <MapSketch />
            </Link>
          </article>
        </div>
      </section>

      {/* ─── Semtler: gerçek ilanlardan hesaplanmış küçük bir çizelge ─── */}
      {districtStats.length > 0 && (
        <section className="border-t border-border">
          <div className="max-w-6xl mx-auto px-5 md:px-8 py-16 grid lg:grid-cols-12 gap-8">
            <div className="lg:col-span-4">
              <h2 className="text-3xl md:text-4xl text-foreground">{t("landing.districtsTitle")}</h2>
              <p className="text-muted-foreground mt-2 max-w-xs">{t("landing.districtsSub")}</p>
            </div>
            <div className="lg:col-span-8 paper-grid rounded-2xl border border-border overflow-hidden">
              <table className="w-full text-left">
                <thead>
                  <tr className="text-sm text-muted-foreground border-b border-border bg-card/80">
                    <th className="font-medium py-3 px-5">{t("landing.colDistrict")}</th>
                    <th className="font-medium py-3 px-5 text-right">{t("landing.colMedian")}</th>
                  </tr>
                </thead>
                <tbody>
                  {districtStats.map(d => (
                    <tr key={d.name} className="border-b border-border/70 last:border-0">
                      <td className="py-3 px-5">
                        <button onClick={() => navigate(browsePath)} className="font-display text-lg text-foreground hover:text-secondary transition-colors">
                          {d.name}
                        </button>
                      </td>
                      <td className="py-3 px-5 text-right tabular-nums text-foreground">
                        {d.median != null ? `${fmtNum(d.median)} TL` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}

      {/* ─── Alt bilgi ─── */}
      <footer className="border-t border-border">
        <div className="max-w-6xl mx-auto px-5 md:px-8 py-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <Wordmark size="sm" />
          <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted-foreground">
            <Link to="/safety" className="hover:text-foreground transition-colors">{t("landing.safety")}</Link>
            <Link to="/explore" className="hover:text-foreground transition-colors">{t("landing.budgetMap")}</Link>
            <Link to="/swipe" className="hover:text-foreground transition-colors">{t("landing.footerListings")}</Link>
            {/* Gerçek <a>: semt sayfaları SPA rotası değil, derleme anında
                üretilen statik HTML. Buradaki bağlantı arama motorunun ana
                sayfadan onlara ulaşmasını sağlar (iç bağlantı). */}
            <a href="/semt" className="hover:text-foreground transition-colors">{t("landing.districtPrices")}</a>
            <Link to="/privacy" className="hover:text-foreground transition-colors">{t("landing.privacy")}</Link>
          </div>
          <p className="text-sm text-muted-foreground">© 2026 {BRAND}</p>
        </div>
      </footer>
    </div>
  );
};

export default Index;
