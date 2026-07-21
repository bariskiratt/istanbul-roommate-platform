import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Zap, MapPin, Home, MessageCircle, X, ChevronLeft, ChevronRight, SlidersHorizontal, Star, GraduationCap, DollarSign, BedDouble, Building, Sofa, DoorOpen, Users, Cigarette, Dog, Ban } from "lucide-react";
import BottomNav from "@/components/layout/BottomNav";
import AppHeader from "@/components/layout/AppHeader";
import { Button } from "@/components/ui/button";
import { motion, AnimatePresence } from "framer-motion";
import LifestyleTag from "@/components/LifestyleTag";
import FilterModal from "@/components/FilterModal";

const filters = ["Tümü", "Kadıköy", "Beşiktaş", "Üsküdar", "Şişli", "1+1", "2+1", "3+1"];

const mockListings = [
  {
    id: "l1",
    title: "Kadıköy Moda'da Ferah 2+1",
    district: "Kadıköy",
    roomType: "2+1",
    price: 8500,
    photo: "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=600&h=400&fit=crop",
    photos: [
      "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=600&h=400&fit=crop",
      "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600&h=400&fit=crop",
      "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=600&h=400&fit=crop",
      "https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=600&h=400&fit=crop",
    ],
    tags: ["Sigara içilmez", "Hayvan dostu"],
    university: "Boğaziçi Ü.",
    rating: 4.8,
    owner: {
      name: "Elif Demir",
      photo: "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=200&h=200&fit=crop&crop=face",
      university: "Boğaziçi Üniversitesi",
      department: "Psikoloji",
      bio: "Kitap kurdu, sabahçı biri. Sessiz ve huzurlu bir ev ortamı arıyorum.",
      budget: "6.000 — 9.000 ₺",
      smoking: false, pets: true, alcohol: false, sleep: "erken" as const,
    },
    features: { floor: 3, furnished: true, elevator: true, rooms: "2+1" },
    rules: { smoking: false, pets: true, guests: true },
  },
  {
    id: "l2",
    title: "Beşiktaş'ta Deniz Manzaralı 1+1",
    district: "Beşiktaş",
    roomType: "1+1",
    price: 7000,
    photo: "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=600&h=400&fit=crop",
    photos: [
      "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=600&h=400&fit=crop",
      "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=600&h=400&fit=crop",
      "https://images.unsplash.com/photo-1484154218962-a197022b5858?w=600&h=400&fit=crop",
    ],
    tags: ["Sigara içilmez"],
    university: "İTÜ",
    rating: 4.9,
    owner: {
      name: "Mehmet Kaya",
      photo: "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=200&h=200&fit=crop&crop=face",
      university: "İTÜ",
      department: "Elektrik Mühendisliği",
      bio: "Müzikle ilgileniyorum, gitar çalıyorum.",
      budget: "4.000 — 6.000 ₺",
      smoking: false, pets: false, alcohol: true, sleep: "gece" as const,
    },
    features: { floor: 5, furnished: false, elevator: true, rooms: "1+1" },
    rules: { smoking: false, pets: false, guests: true },
  },
  {
    id: "l3",
    title: "Üsküdar Merkez'de Geniş 3+1",
    district: "Üsküdar",
    roomType: "3+1",
    price: 5500,
    photo: "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600&h=400&fit=crop",
    photos: [
      "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600&h=400&fit=crop",
      "https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=600&h=400&fit=crop",
      "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=600&h=400&fit=crop",
    ],
    tags: ["Hayvan dostu", "Erken yatarım"],
    university: "Marmara Ü.",
    rating: 4.7,
    owner: {
      name: "Zeynep Arslan",
      photo: "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=200&h=200&fit=crop&crop=face",
      university: "Marmara Üniversitesi",
      department: "Hukuk",
      bio: "Staj dönemindeyim, sakin bir ev ortamı tercih ediyorum.",
      budget: "5.000 — 7.500 ₺",
      smoking: false, pets: false, alcohol: false, sleep: "erken" as const,
    },
    features: { floor: 2, furnished: true, elevator: false, rooms: "3+1" },
    rules: { smoking: false, pets: true, guests: false },
  },
];

type ListingType = typeof mockListings[number];

const Listings = () => {
  const navigate = useNavigate();
  const [activeFilter, setActiveFilter] = useState("Tümü");
  const [selectedListing, setSelectedListing] = useState<ListingType | null>(null);
  const [filterOpen, setFilterOpen] = useState(false);

  const filtered = mockListings.filter(l => {
    if (activeFilter === "Tümü") return true;
    return l.district === activeFilter || l.roomType === activeFilter;
  });

  return (
    <div className="min-h-screen bg-background flex flex-col pb-24">
      <AppHeader
        title="Evler"
        rightAction={
          <button onClick={() => setFilterOpen(true)} className="w-10 h-10 rounded-2xl bg-card flex items-center justify-center text-foreground hover:bg-muted transition-colors" style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
            <SlidersHorizontal className="w-5 h-5" />
          </button>
        }
      />

      <div className="px-6 pt-4 pb-2">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-bold text-foreground">Öne Çıkan Evler</h1>
          <span className="px-2.5 py-1 rounded-full text-[10px] font-semibold bg-primary/10 text-primary flex items-center gap-1">
            <Zap className="w-3 h-3" /> Premium İlanlar
          </span>
        </div>
        <p className="text-sm text-muted-foreground mt-1">Premium üyeler tarafından paylaşılan evler</p>
      </div>

      {/* Filter row */}
      <div className="px-6 py-3">
        <div className="flex gap-2 overflow-x-auto no-scrollbar">
          {filters.map(f => (
            <button
              key={f}
              onClick={() => setActiveFilter(f)}
              className={`px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-all ${
                activeFilter === f
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "bg-card border border-border text-foreground hover:border-primary/30"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Listings — 2 col grid desktop, 1 col mobile */}
      <div className="px-6 flex-1">
        {filtered.length === 0 ? (
          <div className="text-center py-16 space-y-3">
            <div className="w-20 h-20 rounded-3xl bg-muted flex items-center justify-center mx-auto">
              <Home className="w-10 h-10 text-muted-foreground" />
            </div>
            <p className="font-semibold text-foreground">Henüz öne çıkan ilan yok.</p>
            <p className="text-sm text-muted-foreground">Premium üye olarak ilanını buraya ekle.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filtered.map(listing => (
              <div
                key={listing.id}
                onClick={() => setSelectedListing(listing)}
                className="card-listing overflow-hidden cursor-pointer hover:shadow-lg transition-shadow"
                style={{ maxHeight: 320 }}
              >
                <div className="h-[180px] overflow-hidden rounded-t-xl">
                  <img
                    src={listing.photo}
                    alt={listing.title}
                    className="w-full h-full object-cover"
                  />
                </div>
                <div className="p-4 space-y-2">
                  <h3 className="font-bold text-[15px] text-foreground truncate">{listing.title}</h3>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1"><MapPin className="w-3 h-3" /> {listing.district}</span>
                    <span>·</span>
                    <span className="flex items-center gap-1"><Home className="w-3 h-3" /> {listing.roomType}</span>
                    <span>·</span>
                    <span className="font-bold text-accent">{listing.price.toLocaleString("tr-TR")} ₺</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex gap-1.5">
                      {listing.tags.slice(0, 2).map(tag => (
                        <span key={tag} className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-muted text-muted-foreground">
                          {tag}
                        </span>
                      ))}
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-primary/10 text-primary">
                        🎓 {listing.university}
                      </span>
                    </div>
                    <button
                      onClick={e => { e.stopPropagation(); setSelectedListing(listing); }}
                      className="text-xs text-primary font-medium hover:underline"
                    >
                      Detayları Gör →
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Premium banner */}
      <div className="sticky bottom-20 mx-6 rounded-2xl p-4 flex items-center gap-3" style={{ background: "linear-gradient(135deg, hsl(var(--lavender)) 0%, hsl(var(--background)) 100%)" }}>
        <div className="flex-1">
          <p className="text-sm font-semibold text-foreground">İlanını öne çıkar, daha fazla kişiye ulaş ⚡</p>
        </div>
        <Button size="sm" onClick={() => navigate("/premium")} className="rounded-full bg-gradient-to-r from-primary to-secondary text-primary-foreground text-xs px-4 shadow-md">
          Premium'a Geç
        </Button>
      </div>

      {/* Listing Detail Modal */}
      <ListingDetailModal listing={selectedListing} onClose={() => setSelectedListing(null)} />

      {/* Filter Modal */}
      <FilterModal open={filterOpen} onClose={() => setFilterOpen(false)} />

      <BottomNav />
    </div>
  );
};

/* ─── Detail Modal ─── */
const ListingDetailModal = ({ listing, onClose }: { listing: ListingType | null; onClose: () => void }) => {
  const navigate = useNavigate();
  const [photoIndex, setPhotoIndex] = useState(0);

  if (!listing) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-end sm:items-center justify-center"
        onClick={onClose}
      >
        <motion.div
          initial={{ y: 100, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 100, opacity: 0 }}
          className="bg-card rounded-t-3xl sm:rounded-2xl w-full sm:max-w-lg max-h-[90vh] overflow-y-auto"
          onClick={e => e.stopPropagation()}
        >
          {/* Close */}
          <div className="sticky top-0 z-10 flex justify-between items-center p-4">
            <div />
            <button onClick={onClose} className="w-8 h-8 rounded-full bg-muted/80 backdrop-blur-sm flex items-center justify-center">
              <X className="w-4 h-4 text-foreground" />
            </button>
          </div>

          {/* Photo gallery */}
          <div className="px-4 -mt-4">
            <div className="relative h-[260px] rounded-xl overflow-hidden">
              <img
                src={listing.photos[photoIndex]}
                alt={listing.title}
                className="w-full h-full object-cover"
              />
              {listing.photos.length > 1 && (
                <>
                  <button
                    onClick={() => setPhotoIndex(i => Math.max(0, i - 1))}
                    className="absolute left-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-card/80 backdrop-blur-sm flex items-center justify-center"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => setPhotoIndex(i => Math.min(listing.photos.length - 1, i + 1))}
                    className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-card/80 backdrop-blur-sm flex items-center justify-center"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                  <div className="absolute bottom-2 left-1/2 -translate-x-1/2 flex gap-1.5">
                    {listing.photos.map((_, i) => (
                      <div key={i} className={`w-2 h-2 rounded-full ${i === photoIndex ? "bg-white" : "bg-white/50"}`} />
                    ))}
                  </div>
                </>
              )}
            </div>
            {/* Thumbnails */}
            <div className="flex gap-2 mt-2 overflow-x-auto">
              {listing.photos.map((p, i) => (
                <button
                  key={i}
                  onClick={() => setPhotoIndex(i)}
                  className={`w-16 h-12 rounded-lg overflow-hidden flex-shrink-0 border-2 transition-all ${i === photoIndex ? "border-primary" : "border-transparent opacity-60"}`}
                >
                  <img src={p} alt="" className="w-full h-full object-cover" />
                </button>
              ))}
            </div>
          </div>

          {/* Info */}
          <div className="p-5 space-y-4">
            <div>
              <h2 className="text-xl font-bold text-foreground">{listing.title}</h2>
              <div className="flex items-center gap-3 mt-1 text-sm text-muted-foreground">
                <span className="flex items-center gap-1"><MapPin className="w-3.5 h-3.5" /> {listing.district}</span>
                <span>·</span>
                <span className="flex items-center gap-1"><BedDouble className="w-3.5 h-3.5" /> {listing.roomType}</span>
                <span>·</span>
                <span className="font-bold text-accent text-base">{listing.price.toLocaleString("tr-TR")} ₺/ay</span>
              </div>
              <div className="flex items-center gap-1 mt-1 text-xs text-muted-foreground">
                <Star className="w-3 h-3 fill-primary text-primary" />
                <span className="font-semibold text-foreground">{listing.rating}</span>
              </div>
            </div>

            <hr className="border-border" />

            {/* Owner */}
            <div>
              <h3 className="text-sm font-bold text-foreground mb-3">İlan Sahibi</h3>
              <div className="flex items-center gap-3 mb-3">
                <img src={listing.owner.photo} alt={listing.owner.name} className="w-12 h-12 rounded-full object-cover" />
                <div>
                  <p className="font-semibold text-foreground text-sm">{listing.owner.name}</p>
                  <p className="text-xs text-muted-foreground">{listing.owner.university} · {listing.owner.department}</p>
                </div>
              </div>
              <div className="flex flex-wrap gap-1.5 mb-3">
                <LifestyleTag type="smoking" value={listing.owner.smoking} />
                <LifestyleTag type="pets" value={listing.owner.pets} />
                <LifestyleTag type="alcohol" value={listing.owner.alcohol} />
                <LifestyleTag type="sleep" value={listing.owner.sleep} />
              </div>
              <div className="flex items-center gap-2 mb-2">
                <DollarSign className="w-3.5 h-3.5 text-accent" />
                <span className="text-xs font-semibold text-foreground">{listing.owner.budget}</span>
              </div>
              <p className="text-xs text-muted-foreground italic">"{listing.owner.bio}"</p>
            </div>

            <hr className="border-border" />

            {/* Features */}
            <div>
              <h3 className="text-sm font-bold text-foreground mb-3">Ev Özellikleri</h3>
              <div className="grid grid-cols-2 gap-y-2 gap-x-4 text-sm">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <BedDouble className="w-4 h-4" /> <span>{listing.features.rooms}</span>
                </div>
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Building className="w-4 h-4" /> <span>{listing.features.floor}. kat</span>
                </div>
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Sofa className="w-4 h-4" /> <span>{listing.features.furnished ? "Eşyalı" : "Eşyasız"}</span>
                </div>
                <div className="flex items-center gap-2 text-muted-foreground">
                  <DoorOpen className="w-4 h-4" /> <span>{listing.features.elevator ? "Asansörlü" : "Asansörsüz"}</span>
                </div>
              </div>

              <h4 className="text-xs font-semibold text-foreground mt-4 mb-2">Kurallar</h4>
              <div className="flex flex-wrap gap-2">
                <span className={`px-3 py-1 rounded-full text-[11px] font-medium ${listing.rules.smoking ? "bg-accent/15 text-foreground" : "bg-muted text-muted-foreground"}`}>
                  {listing.rules.smoking ? "🚬 Sigara serbest" : "🚭 Sigara yasak"}
                </span>
                <span className={`px-3 py-1 rounded-full text-[11px] font-medium ${listing.rules.pets ? "bg-accent/15 text-foreground" : "bg-muted text-muted-foreground"}`}>
                  {listing.rules.pets ? "🐾 Hayvan serbest" : "🚫 Hayvan yasak"}
                </span>
                <span className={`px-3 py-1 rounded-full text-[11px] font-medium ${listing.rules.guests ? "bg-accent/15 text-foreground" : "bg-muted text-muted-foreground"}`}>
                  {listing.rules.guests ? "👥 Misafir serbest" : "🚫 Misafir yasak"}
                </span>
              </div>
            </div>

            {/* CTA */}
            <Button
              onClick={() => navigate("/login")}
              className="w-full h-12 rounded-full bg-gradient-to-r from-primary to-secondary text-primary-foreground font-bold text-sm"
            >
              <MessageCircle className="w-4 h-4 mr-2" /> İletişime Geç
            </Button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

export default Listings;
