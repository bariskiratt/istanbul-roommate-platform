import { useNavigate, Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Home, Search, Shield, Sparkles, Heart, ChevronLeft, ChevronRight, Star, MapPin, BedDouble, ShieldCheck, Lock, User, Layers, Handshake, X, LogOut } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useRef, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";

const quickDistricts = ["Kadıköy", "Beşiktaş", "Üsküdar", "Şişli", "Sarıyer", "Ataşehir"];

const mockProfiles = [
  { name: "Zeynep", age: 22, uni: "İTÜ", dept: "Mimarlık", district: "KADIKÖY", budget: "5.000 — 8.000", tags: ["Sigara içmez", "Düzenli"], photo: "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=400&h=400&fit=crop" },
  { name: "Burak", age: 23, uni: "Boğaziçi", dept: "Bilgisayar Müh.", district: "BEŞİKTAŞ", budget: "6.000 — 9.000", tags: ["Hayvan dostu", "Sessiz"], photo: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&h=400&fit=crop" },
  { name: "Elif", age: 21, uni: "Marmara", dept: "Psikoloji", district: "ÜSKÜDAR", budget: "4.000 — 7.000", tags: ["Sigara içmez", "Sosyal"], photo: "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=400&h=400&fit=crop" },
  { name: "Kaan", age: 24, uni: "Yıldız Teknik", dept: "Elektrik Müh.", district: "ŞİŞLİ", budget: "5.500 — 8.500", tags: ["Düzenli", "Spor sever"], photo: "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=400&h=400&fit=crop" },
  { name: "Sude", age: 20, uni: "İstanbul Ü.", dept: "Hukuk", district: "FATİH", budget: "4.500 — 7.000", tags: ["Sessiz", "Sigara içmez"], photo: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=400&h=400&fit=crop" },
  { name: "Ahmet Durtmez", age: 25, uni: "Koç Üniversitesi", dept: "İşletme", district: "SARIYER", budget: "7.000 — 12.000", tags: ["Hayvan dostu", "Sosyal"], photo: "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=400&h=400&fit=crop" },
];

const mockListings = [
  { title: "Kadıköy'de Ferah 2+1", district: "Kadıköy", rooms: "2+1", price: "7.500", rating: 4.8, photo: "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=600&h=400&fit=crop" },
  { title: "Beşiktaş'ta Deniz Manzaralı 1+1", district: "Beşiktaş", rooms: "1+1", price: "9.000", rating: 4.9, photo: "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600&h=400&fit=crop" },
  { title: "Üsküdar Merkez'de Geniş 3+1", district: "Üsküdar", rooms: "3+1", price: "5.500", rating: 4.7, photo: "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=600&h=400&fit=crop" },
  { title: "Şişli'de Yeni Tadilatlı 2+1", district: "Şişli", rooms: "2+1", price: "8.200", rating: 4.6, photo: "https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=600&h=400&fit=crop" },
  { title: "Sarıyer'de Doğa İçinde 1+1", district: "Sarıyer", rooms: "1+1", price: "6.000", rating: 4.5, photo: "https://images.unsplash.com/photo-1484154218962-a197022b5858?w=600&h=400&fit=crop" },
];

const districtGrid = [
  { name: "Kadıköy", photo: "https://images.unsplash.com/photo-1524231757912-21f4fe3a7200?w=400&h=300&fit=crop" },
  { name: "Beşiktaş", photo: "https://images.unsplash.com/photo-1527838832700-5059252407fa?w=400&h=300&fit=crop" },
  { name: "Üsküdar", photo: "https://images.unsplash.com/photo-1541432901042-2d8bd64b4a9b?w=400&h=300&fit=crop" },
  { name: "Şişli", photo: "https://images.unsplash.com/photo-1569336415962-a4bd9f69cd83?w=400&h=300&fit=crop" },
  { name: "Sarıyer", photo: "https://images.unsplash.com/photo-1564594736624-def7a10ab047?w=400&h=300&fit=crop" },
  { name: "Ataşehir", photo: "https://images.unsplash.com/photo-1477959858617-67f85cf4f1df?w=400&h=300&fit=crop" },
  { name: "Fatih", photo: "https://images.unsplash.com/photo-1541432901042-2d8bd64b4a9b?w=400&h=300&fit=crop" },
  { name: "Bakırköy", photo: "https://images.unsplash.com/photo-1449824913935-59a10b8d2000?w=400&h=300&fit=crop" },
  { name: "Maltepe", photo: "https://images.unsplash.com/photo-1464938050520-ef2571e0d6e0?w=400&h=300&fit=crop" },
  { name: "Beyoğlu", photo: "https://images.unsplash.com/photo-1527838832700-5059252407fa?w=400&h=300&fit=crop" },
];

const mapPins: Array<{ id: number; district: string; price: string; top: string; left: string; rotate: number; title: string; rooms: string; rating: number; reviews: number; photo: string; expandedByDefault?: boolean; cardDirection?: "up" | "down"; cardAlign?: "left" | "center" }> = [
  { id: 1, district: "Kadıköy", price: "6.200 ₺", top: "12%", left: "6%", rotate: -1, title: "Kadıköy Moda'da 2+1", rooms: "2+1", rating: 4.7, reviews: 18, photo: "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=300&h=180&fit=crop", cardDirection: "down" },
  { id: 4, district: "Şişli", price: "7.200 ₺", top: "12%", left: "82%", rotate: 1, title: "Şişli Merkez'de 2+1", rooms: "2+1", rating: 4.8, reviews: 31, photo: "https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=300&h=180&fit=crop", cardDirection: "down", cardAlign: "left" },
  { id: 5, district: "Fatih", price: "4.900 ₺", top: "45%", left: "4%", rotate: -1, title: "Fatih'te Tarihi 1+1", rooms: "1+1", rating: 4.5, reviews: 9, photo: "https://images.unsplash.com/photo-1484154218962-a197022b5858?w=300&h=180&fit=crop" },
  { id: 3, district: "Üsküdar", price: "5.800 ₺", top: "45%", left: "84%", rotate: -2, title: "Üsküdar'da Geniş 3+1", rooms: "3+1", rating: 4.6, reviews: 12, photo: "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=300&h=180&fit=crop", expandedByDefault: true, cardAlign: "left" },
  { id: 7, district: "Ataşehir", price: "5.500 ₺", top: "80%", left: "5%", rotate: 2, title: "Ataşehir'de Modern 1+1", rooms: "1+1", rating: 4.4, reviews: 7, photo: "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=300&h=180&fit=crop" },
  { id: 6, district: "Sarıyer", price: "8.100 ₺", top: "80%", left: "85%", rotate: -2, title: "Sarıyer'de Orman Manzaralı 2+1", rooms: "2+1", rating: 4.7, reviews: 15, photo: "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=300&h=180&fit=crop", cardAlign: "left" },
];

const Index = () => {
  const navigate = useNavigate();
  const { isLoggedIn, logout } = useAuth();
  const profilesRef = useRef<HTMLDivElement>(null);
  const listingsRef = useRef<HTMLDivElement>(null);
  const [searchType, setSearchType] = useState("Ev arkadaşı");
  const [hoveredPin, setHoveredPin] = useState<number | null>(null);

  const scroll = (ref: React.RefObject<HTMLDivElement>, dir: "left" | "right") => {
    ref.current?.scrollBy({ left: dir === "left" ? -320 : 320, behavior: "smooth" });
  };

  return (
    <div className="min-h-screen bg-background">
      {/* ─── NAVBAR ─── */}
      <nav className="sticky top-0 z-50 bg-card/95 backdrop-blur-lg border-b border-border">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 cursor-pointer">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
              <Home className="w-4 h-4 text-primary-foreground" />
            </div>
            <span className="font-extrabold text-lg text-foreground tracking-tight">RoomMatch</span>
          </Link>
          <div className="hidden md:flex items-center gap-8 text-sm font-medium text-muted-foreground">
            <button onClick={() => navigate("/listings")} className="hover:text-foreground transition-colors">Ev Bul</button>
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

      {/* ─── HERO ─── */}
      <section className="relative min-h-[580px] overflow-hidden">
        {/* Static Istanbul Map Background */}
        <div className="absolute inset-0">
          <img
            src="/images/istanbul-map.png"
            alt="Istanbul map"
            className="w-full h-full object-cover object-center"
          />
          {/* Blue tint overlay */}
          <div className="absolute inset-0" style={{ background: 'rgba(61, 127, 245, 0.70)' }} />
        </div>

        {/* Floating price pins */}
        <div className="absolute inset-0 hidden md:block">
          {mapPins.map((pin, i) => {
            const isExpanded = pin.expandedByDefault || hoveredPin === pin.id;
            return (
              <motion.div
                key={pin.id}
                className="absolute z-10"
                style={{ top: pin.top, left: pin.left }}
                initial={{ opacity: 0, scale: 0.7 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.5 + i * 0.2, duration: 0.4 }}
              >
                {/* Float animation wrapper */}
                <motion.div
                  animate={{ y: [0, -4, 0] }}
                  transition={{ duration: 3, repeat: Infinity, delay: i * 0.4, ease: "easeInOut" }}
                  onMouseEnter={() => setHoveredPin(pin.id)}
                  onMouseLeave={() => setHoveredPin(null)}
                  className="relative"
                >
                  {/* Expanded card - Airbnb style */}
                  <AnimatePresence>
                    {isExpanded && (
                      <motion.div
                        initial={{ opacity: 0, y: pin.cardDirection === "down" ? -10 : 10, scale: 0.9 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: pin.cardDirection === "down" ? -10 : 10, scale: 0.9 }}
                        transition={{ duration: 0.2 }}
                        className={`absolute ${pin.cardDirection === "down" ? "top-full mt-2" : "bottom-full mb-2"} ${pin.cardAlign === "left" ? "right-0" : "left-1/2 -translate-x-1/2"} w-[200px] bg-card rounded-xl shadow-2xl overflow-hidden z-30 cursor-pointer`}
                        onClick={() => navigate("/listings")}
                      >
                        <div className="relative">
                          <img src={pin.photo} alt={pin.title} className="w-full h-[100px] object-cover rounded-t-xl" />
                          <div className="absolute top-2 right-2 flex gap-1.5">
                            <button className="w-7 h-7 rounded-full bg-card/90 backdrop-blur-sm flex items-center justify-center shadow-sm hover:bg-card transition-colors">
                              <Heart className="w-3 h-3 text-foreground" />
                            </button>
                            <button className="w-7 h-7 rounded-full bg-card/90 backdrop-blur-sm flex items-center justify-center shadow-sm hover:bg-card transition-colors">
                              <X className="w-3 h-3 text-foreground" />
                            </button>
                          </div>
                        </div>
                        <div className="p-3 space-y-1">
                          <p className="text-xs font-bold text-foreground leading-tight truncate">{pin.title}</p>
                          <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
                            <Star className="w-2.5 h-2.5 fill-foreground text-foreground" />
                            <span className="font-semibold text-foreground">{pin.rating}</span>
                          </div>
                          <p className="text-xs font-bold text-accent">{pin.price}<span className="font-normal text-muted-foreground">/ay</span></p>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>

                  {/* Price pill */}
                  <div
                    className="px-3 py-1.5 rounded-full bg-card text-foreground text-xs font-bold shadow-lg cursor-pointer hover:scale-110 transition-transform whitespace-nowrap"
                    style={{ transform: `rotate(${pin.rotate}deg)` }}
                    onClick={() => navigate("/listings")}
                  >
                    {pin.price}
                  </div>
                </motion.div>
              </motion.div>
            );
          })}
        </div>

        {/* Hero content */}
        <div className="relative z-20 py-16 md:py-24 px-6">
          <div className="max-w-4xl mx-auto text-center space-y-5">
            <motion.h1
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ duration: 0.5 }}
              className="text-3xl md:text-5xl font-extrabold text-white leading-tight drop-shadow-lg"
            >
              Ev arkadaşını bul,<br />yeni hayatına başla.
            </motion.h1>
            <motion.p
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.15, duration: 0.5 }}
              className="text-white/85 text-base md:text-lg max-w-xl mx-auto drop-shadow"
            >
              Üniversite öğrencileri için güvenli, doğrulanmış eşleşme platformu.
            </motion.p>

            {/* Trust badges */}
            <motion.div
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.22, duration: 0.5 }}
              className="flex flex-wrap justify-center gap-3 pt-2"
            >
              <span className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full text-xs font-semibold" style={{ background: 'rgba(217, 215, 255, 0.9)', color: '#6371F4' }}>
                <ShieldCheck className="w-3.5 h-3.5" />
                Sadece .edu.tr uzantılı üniversite e-postasıyla kayıt
              </span>
              <span className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full text-xs font-semibold" style={{ background: 'rgba(217, 215, 255, 0.9)', color: '#6371F4' }}>
                <Lock className="w-3.5 h-3.5" />
                Doğrulanmış öğrenci topluluğu
              </span>
            </motion.div>

            {/* Search bar */}
            <motion.div
              initial={{ y: 30, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.3, duration: 0.5 }}
              className="bg-card rounded-full shadow-2xl max-w-3xl mx-auto flex items-center overflow-hidden mt-8 ring-1 ring-white/20"
            >
              <div className="flex-1 px-5 py-4 border-r border-border">
                <div className="text-xs font-semibold text-foreground">Nerede?</div>
                <input className="w-full text-sm text-muted-foreground bg-transparent outline-none mt-0.5 placeholder:text-muted-foreground/60" placeholder="Semt veya üniversite ara..." />
              </div>
              <div className="flex-1 px-5 py-4 border-r border-border hidden sm:block">
                <div className="text-xs font-semibold text-foreground">Bütçe</div>
                <input className="w-full text-sm text-muted-foreground bg-transparent outline-none mt-0.5 placeholder:text-muted-foreground/60" placeholder="Min ₺ — Max ₺" />
              </div>
              <div className="flex-1 px-5 py-4 hidden sm:block">
                <div className="text-xs font-semibold text-foreground">Arıyorum</div>
                <select
                  value={searchType}
                  onChange={(e) => setSearchType(e.target.value)}
                  className="w-full text-sm text-muted-foreground bg-transparent outline-none mt-0.5"
                >
                  <option>Ev arkadaşı</option>
                  <option>Ev</option>
                  <option>İkisi de</option>
                </select>
              </div>
              <button
                onClick={() => navigate("/swipe")}
                className="w-14 h-14 bg-primary rounded-full flex items-center justify-center flex-shrink-0 mr-1.5 hover:opacity-90 transition-opacity"
              >
                <Search className="w-5 h-5 text-primary-foreground" />
              </button>
            </motion.div>

            {/* Quick pills */}
            <div className="flex flex-wrap justify-center gap-2 pt-4">
              {quickDistricts.map((d) => (
                <button
                  key={d}
                  onClick={() => navigate("/listings")}
                  className="px-4 py-1.5 rounded-full text-xs font-medium bg-white/15 text-white hover:bg-white/25 transition-colors backdrop-blur-sm"
                >
                  {d}
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ─── SECTION 1: Ev Arkadaşı Ara ─── */}
      <section className="max-w-7xl mx-auto px-6 py-16">
        <div className="flex items-end justify-between mb-8">
          <div>
            <h2 className="text-2xl md:text-3xl font-extrabold text-foreground">Ev Arkadaşı Ara</h2>
            <p className="text-muted-foreground mt-1">Yaşam tarzına uygun birini bul</p>
          </div>
          <div className="flex gap-2">
            <button onClick={() => scroll(profilesRef, "left")} className="w-9 h-9 rounded-full border border-border bg-card flex items-center justify-center hover:bg-muted transition-colors">
              <ChevronLeft className="w-4 h-4 text-foreground" />
            </button>
            <button onClick={() => scroll(profilesRef, "right")} className="w-9 h-9 rounded-full border border-border bg-card flex items-center justify-center hover:bg-muted transition-colors">
              <ChevronRight className="w-4 h-4 text-foreground" />
            </button>
          </div>
        </div>
        <div ref={profilesRef} className="flex gap-5 overflow-x-auto scrollbar-hide pb-4 -mx-2 px-2 snap-x">
          {mockProfiles.map((p, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.05 }}
              className="flex-shrink-0 w-52 snap-start"
            >
              <div onClick={() => navigate("/swipe")} className="card-listing overflow-hidden group cursor-pointer">
                <div className="aspect-square overflow-hidden">
                  <img src={p.photo} alt={p.name} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" />
                </div>
                <div className="p-4 space-y-2">
                  <h3 className="font-bold text-foreground">{p.name}</h3>
                  <p className="text-xs text-muted-foreground">{p.uni} · {p.dept}</p>
                  <p className="text-[10px] font-semibold tracking-widest text-muted-foreground">{p.district}</p>
                  <div className="flex flex-wrap gap-1">
                    {p.tags.map((t) => (
                      <span key={t} className="tag-lifestyle text-[10px] px-2 py-0.5">{t}</span>
                    ))}
                  </div>
                  <p className="text-xs font-bold text-accent">{p.budget} ₺/ay</p>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ─── SECTION 2: Öne Çıkan Evler ─── */}
      <section className="max-w-7xl mx-auto px-6 py-16">
        <div className="flex items-end justify-between mb-8">
          <button onClick={() => navigate("/listings")} className="group">
            <h2 className="text-2xl md:text-3xl font-extrabold text-foreground inline-flex items-center gap-2">
              Öne Çıkan Evler
              <ChevronRight className="w-6 h-6 text-muted-foreground group-hover:translate-x-1 transition-transform" />
            </h2>
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
          {mockListings.map((l, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.05 }}
              className="flex-shrink-0 w-72 snap-start"
            >
              <div onClick={() => navigate("/listings")} className="card-listing overflow-hidden group cursor-pointer">
                <div className="relative aspect-[4/3] overflow-hidden">
                  <img src={l.photo} alt={l.title} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" />
                  <span className="absolute top-3 left-3 bg-secondary/90 text-secondary-foreground text-[10px] font-semibold px-2.5 py-1 rounded-full backdrop-blur-sm">
                    Ev İlanı
                  </span>
                  <button className="absolute top-3 right-3 w-8 h-8 rounded-full bg-card/70 backdrop-blur-sm flex items-center justify-center hover:bg-card transition-colors">
                    <Heart className="w-4 h-4 text-foreground" />
                  </button>
                </div>
                <div className="p-4 space-y-1.5">
                  <h3 className="font-bold text-foreground text-sm">{l.title}</h3>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <MapPin className="w-3 h-3" /> {l.district}
                    <span>·</span>
                    <BedDouble className="w-3 h-3" /> {l.rooms}
                  </div>
                  <div className="flex items-center justify-between pt-1">
                    <span className="font-bold text-foreground">{l.price} ₺<span className="font-normal text-muted-foreground text-xs">/ay</span></span>
                    <span className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Star className="w-3 h-3 fill-primary text-primary" /> {l.rating}
                    </span>
                  </div>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ─── SECTION: Nasıl Çalışır? ─── */}
      <section id="nasil-calisir" className="py-20 px-6" style={{ background: 'linear-gradient(180deg, #F8F7FA 0%, #EEF2FF 100%)' }}>
        <div className="max-w-6xl mx-auto">
          {/* Header */}
          <div className="text-center mb-16">
            <p className="text-xs font-bold tracking-[0.25em] uppercase mb-3" style={{ color: '#6371F4' }}>
              3 ADIMDA EV ARKADAŞI BUL
            </p>
            <h2 className="text-3xl md:text-4xl font-extrabold" style={{ color: '#1A1A2E' }}>
              Bu kadar basit.
            </h2>
          </div>

          {/* Step cards */}
          <div className="grid md:grid-cols-3 gap-8 relative">
            {/* Connecting dashed lines (desktop) */}
            <div className="hidden md:block absolute top-24 left-[33%] w-[34%] border-t-2 border-dashed" style={{ borderColor: '#D9D7FF' }} />

            {/* Step 1 */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: 0 }}
              className="relative bg-card rounded-2xl p-8 shadow-md hover:shadow-lg hover:scale-[1.02] transition-all duration-300"
            >
              <span className="absolute -top-4 -left-2 text-7xl font-extrabold text-muted-foreground/10 select-none">01</span>
              <div className="w-16 h-16 rounded-2xl flex items-center justify-center mb-5" style={{ background: 'linear-gradient(135deg, #3D7FF5, #6371F4)' }}>
                <User className="w-7 h-7 text-white" />
              </div>
              <h3 className="text-lg font-bold text-foreground mb-2">Profilini Oluştur</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Üniversite e-postanla kayıt ol. Bütçeni, yaşam tarzını ve tercih ettiğin semti belirt.
              </p>
              <div className="flex gap-2 mt-5">
                {[0, 1, 2].map((dot) => (
                  <motion.div
                    key={dot}
                    className="w-2.5 h-2.5 rounded-full"
                    style={{ background: '#D9D7FF' }}
                    initial={{ scale: 0.5, opacity: 0.3 }}
                    whileInView={{ scale: 1, opacity: 1, background: '#3D7FF5' }}
                    viewport={{ once: true }}
                    transition={{ delay: dot * 0.3 + 0.5, duration: 0.4 }}
                  />
                ))}
              </div>
            </motion.div>

            {/* Step 2 */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: 0.15 }}
              className="relative bg-card rounded-2xl p-8 shadow-md hover:shadow-lg hover:scale-[1.02] transition-all duration-300"
            >
              <span className="absolute -top-4 -left-2 text-7xl font-extrabold text-muted-foreground/10 select-none">02</span>
              <div className="w-16 h-16 rounded-2xl flex items-center justify-center mb-5" style={{ background: 'linear-gradient(135deg, #6371F4, #3D7FF5)' }}>
                <Layers className="w-7 h-7 text-white" />
              </div>
              <h3 className="text-lg font-bold text-foreground mb-2">Keşfet & Swipe At</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Ev fotoğraflarını gör, beğendiklerine sağa swipe at. Ev sahipleri senin profilini değerlendirir.
              </p>
              {/* Mini card stack animation */}
              <div className="relative h-10 mt-5 flex items-end gap-1">
                {[0, 1, 2].map((card) => (
                  <motion.div
                    key={card}
                    className="w-8 h-10 rounded-lg shadow-sm"
                    style={{ background: card === 0 ? '#3D7FF5' : card === 1 ? '#6371F4' : '#D9D7FF', position: 'absolute', left: card * 10 }}
                    initial={{ x: 0, rotate: 0 }}
                    whileInView={card === 0 ? { x: [0, 30, 30], rotate: [0, 5, 5], opacity: [1, 1, 0] } : {}}
                    viewport={{ once: true }}
                    transition={{ delay: 1, duration: 1.2, repeat: Infinity, repeatDelay: 2 }}
                  />
                ))}
              </div>
            </motion.div>

            {/* Step 3 */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: 0.3 }}
              className="relative bg-card rounded-2xl p-8 shadow-md hover:shadow-lg hover:scale-[1.02] transition-all duration-300"
            >
              <span className="absolute -top-4 -left-2 text-7xl font-extrabold text-muted-foreground/10 select-none">03</span>
              <div className="w-16 h-16 rounded-2xl flex items-center justify-center mb-5" style={{ background: 'linear-gradient(135deg, #4DE1C1, #3D7FF5)' }}>
                <Handshake className="w-7 h-7 text-white" />
              </div>
              <h3 className="text-lg font-bold text-foreground mb-2">Eşleş & Tanış</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Karşılıklı beğeni sonrası eşleşme gerçekleşir. Uygulama içi mesajlaşmayla iletişime geç.
              </p>
              {/* Confetti burst */}
              <div className="relative h-10 mt-5 flex items-center justify-center">
                {['#4DE1C1', '#D9D7FF', '#FF6F61', '#3D7FF5', '#6371F4', '#4DE1C1'].map((color, i) => (
                  <motion.div
                    key={i}
                    className="absolute w-2 h-2 rounded-full"
                    style={{ background: color }}
                    initial={{ scale: 0, x: 0, y: 0 }}
                    whileInView={{
                      scale: [0, 1, 0],
                      x: [0, (i % 2 === 0 ? 1 : -1) * (10 + i * 8)],
                      y: [0, -(10 + (i % 3) * 12)],
                    }}
                    viewport={{ once: true }}
                    transition={{ delay: 0.8 + i * 0.08, duration: 0.8 }}
                  />
                ))}
              </div>
            </motion.div>
          </div>

          {/* Vertical dashed line for mobile */}
          <div className="md:hidden flex justify-center my-0">
            <div className="w-px h-0 border-l-2 border-dashed" style={{ borderColor: '#D9D7FF' }} />
          </div>

          {/* CTA */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.4, duration: 0.5 }}
            className="text-center mt-16 space-y-4"
          >
            <p className="text-lg font-semibold text-foreground">Hemen başla, ilk eşleşmeni bul.</p>
            <Button
              onClick={() => navigate("/onboarding")}
              className="rounded-full text-white font-bold px-8 py-4 text-base h-auto"
              style={{ background: 'linear-gradient(135deg, #3D7FF5, #6371F4)' }}
            >
              Ücretsiz Kaydol →
            </Button>
            <p className="text-xs text-muted-foreground">
              Kredi kartı gerekmez · Tamamen ücretsiz · .edu.tr gerekli
            </p>
          </motion.div>
        </div>
      </section>

      {/* ─── SECTION 3: District Grid ─── */}
      <section className="max-w-7xl mx-auto px-6 py-16">
        <h2 className="text-2xl md:text-3xl font-extrabold text-foreground text-center mb-10">İstanbul'da Ev Ara</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-4">
          {districtGrid.map((d, i) => (
            <motion.div
              key={d.name}
              initial={{ opacity: 0, scale: 0.95 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.03 }}
              className="group cursor-pointer"
              onClick={() => navigate("/listings")}
            >
              <div className="aspect-[4/3] rounded-xl overflow-hidden">
                <img src={d.photo} alt={d.name} className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-300" />
              </div>
              <p className="text-sm font-bold text-foreground text-center mt-2">{d.name}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ─── SECTION 4: Features ─── */}
      <section className="max-w-5xl mx-auto px-6 py-16">
        <div className="grid md:grid-cols-3 gap-10">
          {[
            { icon: Home, title: "Önce Ev, Sonra Kişi", desc: "İlanları ve ev fotoğraflarını gör, beğendiklerine swipe at." },
            { icon: Shield, title: ".edu.tr ile Güvende", desc: "Sadece doğrulanmış üniversite öğrencileri. Sahte profil yok." },
            { icon: Sparkles, title: "Uyum Bazlı Eşleşme", desc: "Bütçe, yaşam tarzı ve konum kriterlerine göre akıllı eşleşme." },
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
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
              <Home className="w-3.5 h-3.5 text-primary-foreground" />
            </div>
            <span className="font-extrabold text-foreground">RoomMatch</span>
          </div>
          <div className="flex gap-6 text-sm text-muted-foreground">
            <button onClick={() => navigate("/safety")} className="hover:text-foreground transition-colors">Hakkımızda</button>
            <button onClick={() => navigate("/safety")} className="hover:text-foreground transition-colors">Gizlilik</button>
            <button onClick={() => navigate("/safety")} className="hover:text-foreground transition-colors">Kullanım Koşulları</button>
            <button onClick={() => navigate("/login")} className="hover:text-foreground transition-colors">İletişim</button>
          </div>
          <p className="text-xs text-muted-foreground">© 2025 RoomMatch. Tüm hakları saklıdır.</p>
        </div>
      </footer>
    </div>
  );
};

export default Index;
