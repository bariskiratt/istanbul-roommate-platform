import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import {
  ArrowLeft, ArrowRight, Camera, Check, Home, User, MapPin,
  Cigarette, Dog, X, Plus, ImagePlus, FileText
} from "lucide-react";
import { toast } from "@/hooks/use-toast";
import FairPriceCheck from "@/components/FairPriceCheck";

type ListingType = "ev_ilani" | "kisisel_ilan" | null;

const CreateListing = () => {
  const navigate = useNavigate();

  // Step 0: type selection, then form
  const [listingType, setListingType] = useState<ListingType>(null);
  const [currentStep, setCurrentStep] = useState(0);

  // Common fields
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [district, setDistrict] = useState("");
  const [photos, setPhotos] = useState<string[]>([]);

  // Ev ilanı fields
  const [rent, setRent] = useState("");
  const [roomCount, setRoomCount] = useState("");
  const [smokingAllowed, setSmokingAllowed] = useState(false);
  const [petsAllowed, setPetsAllowed] = useState(false);

  // Kişisel ilan fields
  const [budget, setBudget] = useState([4000, 8000]);

  const isHouse = listingType === "ev_ilani";

  const stepsForType = listingType === "ev_ilani"
    ? ["Detaylar", "Kurallar", "Konum", "Fotoğraflar"]
    : ["Detaylar", "Bütçe", "Konum", "Fotoğraflar"];

  const totalSteps = stepsForType.length;
  const progress = ((currentStep + 1) / totalSteps) * 100;

  const handlePhotoAdd = () => {
    const mockPhotos = [
      "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=400&h=300&fit=crop",
      "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=400&h=300&fit=crop",
      "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=400&h=300&fit=crop",
    ];
    if (photos.length < 6) {
      setPhotos([...photos, mockPhotos[photos.length % mockPhotos.length]]);
    }
  };

  const removePhoto = (index: number) => {
    setPhotos(photos.filter((_, i) => i !== index));
  };

  const canProceed = () => {
    if (currentStep === 0) return title.length > 0 && description.length > 0 && (isHouse ? rent && roomCount : true);
    if (currentStep === 1) return true;
    if (currentStep === 2) return district !== "";
    if (currentStep === 3) return photos.length >= 1;
    return false;
  };

  const handleSubmit = () => {
    toast({
      title: "İlan Oluşturuldu! 🎉",
      description: `"${title}" başarıyla yayınlandı.`,
    });
    navigate("/profile");
  };

  const next = () => {
    if (currentStep === totalSteps - 1) {
      handleSubmit();
    } else {
      setCurrentStep(s => s + 1);
    }
  };

  const back = () => {
    if (currentStep > 0) {
      setCurrentStep(s => s - 1);
    } else {
      setListingType(null);
    }
  };

  // Type selection screen
  if (!listingType) {
    return (
      <div className="min-h-screen bg-background flex flex-col">
        <div className="px-6 pt-4 pb-2 flex items-center gap-3">
          <button
            onClick={() => navigate(-1)}
            className="w-10 h-10 rounded-full bg-card flex items-center justify-center text-foreground hover:bg-muted transition-colors"
            style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h1 className="font-bold text-xl text-foreground">İlan Oluştur</h1>
        </div>

        <div className="flex-1 px-6 pt-8 space-y-6">
          <div className="text-center space-y-3">
            <div className="w-16 h-16 rounded-2xl bg-lavender/50 flex items-center justify-center mx-auto">
              <FileText className="w-8 h-8 text-primary" />
            </div>
            <h2 className="text-[28px] font-bold text-foreground">Ne tür bir ilan?</h2>
            <p className="text-muted-foreground text-sm max-w-[280px] mx-auto">
              Ev ilanı veya kişisel ilan oluşturabilirsin
            </p>
          </div>

          <div className="space-y-4 pt-4">
            <motion.button
              whileTap={{ scale: 0.98 }}
              onClick={() => { setListingType("ev_ilani"); setCurrentStep(0); }}
              className="w-full card-listing p-6 flex items-center gap-5 text-left hover:shadow-lg transition-shadow"
            >
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center flex-shrink-0">
                <Home className="w-8 h-8 text-primary" />
              </div>
              <div>
                <h3 className="font-bold text-lg text-foreground">Ev İlanı</h3>
                <p className="text-sm text-muted-foreground mt-1">Evin var, ev arkadaşı arıyorsun</p>
              </div>
              <ArrowRight className="w-5 h-5 text-muted-foreground ml-auto" />
            </motion.button>

            <motion.button
              whileTap={{ scale: 0.98 }}
              onClick={() => { setListingType("kisisel_ilan"); setCurrentStep(0); }}
              className="w-full card-listing p-6 flex items-center gap-5 text-left hover:shadow-lg transition-shadow"
            >
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-accent/20 to-accent/5 flex items-center justify-center flex-shrink-0">
                <User className="w-8 h-8 text-accent" />
              </div>
              <div>
                <h3 className="font-bold text-lg text-foreground">Kişisel İlan</h3>
                <p className="text-sm text-muted-foreground mt-1">Ev arıyorsun, bütçeni paylaş</p>
              </div>
              <ArrowRight className="w-5 h-5 text-muted-foreground ml-auto" />
            </motion.button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Top bar */}
      <div className="px-6 pt-4 pb-2 flex items-center gap-3">
        <button
          onClick={back}
          className="w-10 h-10 rounded-full bg-card flex items-center justify-center text-foreground hover:bg-muted transition-colors"
          style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1">
          <span className={`text-[10px] px-2.5 py-1 rounded-full font-medium ${
            isHouse ? "bg-lavender/50 text-foreground" : "bg-accent/15 text-foreground"
          }`}>
            {isHouse ? "🏠 Ev İlanı" : "👤 Kişisel İlan"}
          </span>
        </div>
      </div>

      {/* Progress */}
      <div className="px-6 pb-2">
        <div className="h-[3px] w-full bg-muted rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-gradient-to-r from-primary to-secondary rounded-full"
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.5, ease: "easeOut" }}
          />
        </div>
      </div>

      {/* Content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={currentStep}
          initial={{ opacity: 0, x: 30 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -30 }}
          transition={{ duration: 0.3 }}
          className="flex-1 px-6 pb-32 overflow-y-auto"
        >
          {/* Step 0: Details */}
          {currentStep === 0 && (
            <div className="space-y-5 pt-6">
              <div className="text-center space-y-2 pb-4">
                <h2 className="text-[28px] font-bold text-foreground">İlan Detayları</h2>
                <p className="text-muted-foreground text-sm">Temel bilgileri doldur</p>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">Başlık</label>
                <Input
                  placeholder={isHouse ? "İlanına çekici bir başlık ver (ör. Kadıköy'de güneşli 2+1)" : "Kısa ve dikkat çekici bir başlık (ör. Kadıköy'de ev arkadaşı arıyorum)"}
                  value={title}
                  onChange={e => setTitle(e.target.value)}
                  className="h-14 text-base rounded-2xl bg-card border-border shadow-sm focus:shadow-md focus:ring-2 focus:ring-primary/20 transition-shadow"
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">Açıklama</label>
                <textarea
                  placeholder="Evin özelliklerini anlat, potansiyel ev arkadaşına ne söylemek istersin?"
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                  rows={4}
                  className="w-full rounded-2xl bg-card border border-border px-4 py-3 text-base text-foreground placeholder:text-muted-foreground shadow-sm focus:shadow-md focus:ring-2 focus:ring-primary/20 transition-shadow outline-none resize-none"
                />
              </div>

              {isHouse && (
                <>
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-foreground">Aylık Kira (₺)</label>
                    <Input
                      type="number"
                      placeholder="Aylık kira (₺)"
                      value={rent}
                      onChange={e => setRent(e.target.value)}
                      className="h-14 text-base rounded-2xl bg-card border-border shadow-sm focus:shadow-md focus:ring-2 focus:ring-primary/20 transition-shadow"
                    />
                  </div>
                  <div className="space-y-3">
                    <label className="text-sm font-medium text-foreground">Oda Sayısı</label>
                    <div className="grid grid-cols-4 gap-3">
                      {["1+0", "1+1", "2+1", "3+1"].map(r => (
                        <button
                          key={r}
                          onClick={() => setRoomCount(r)}
                          className={`p-4 rounded-2xl border-2 text-sm font-bold transition-all ${
                            roomCount === r
                              ? "border-secondary bg-lavender/30 shadow-md"
                              : "border-border bg-card hover:border-primary/30 hover:shadow-sm"
                          }`}
                        >
                          {r}
                        </button>
                      ))}
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

          {/* Step 1: Rules (ev) or Budget (kişisel) */}
          {currentStep === 1 && isHouse && (
            <div className="space-y-5 pt-6">
              <div className="text-center space-y-2 pb-4">
                <h2 className="text-[28px] font-bold text-foreground">Ev Kuralları</h2>
                <p className="text-muted-foreground text-sm">Ev arkadaşının bilmesi gerekenler</p>
              </div>

              {[
                { key: "smoking", icon: Cigarette, label: "Sigara İzni", desc: "Evde sigara içilebilir mi?", value: smokingAllowed, setValue: setSmokingAllowed },
                { key: "pets", icon: Dog, label: "Evcil Hayvan", desc: "Evcil hayvan kabul ediliyor mu?", value: petsAllowed, setValue: setPetsAllowed },
              ].map(item => (
                <button
                  key={item.key}
                  onClick={() => item.setValue(!item.value)}
                  className={`w-full flex items-center gap-4 p-5 rounded-2xl border-2 transition-all ${
                    item.value
                      ? "border-primary bg-primary/5 shadow-md"
                      : "border-border bg-card hover:shadow-sm"
                  }`}
                >
                  <div className={`w-12 h-12 rounded-2xl flex items-center justify-center transition-colors ${
                    item.value ? "bg-primary text-primary-foreground" : "bg-lavender/50 text-muted-foreground"
                  }`}>
                    <item.icon className="w-6 h-6" />
                  </div>
                  <div className="flex-1 text-left">
                    <p className="font-semibold text-foreground">{item.label}</p>
                    <p className="text-xs text-muted-foreground">{item.desc}</p>
                  </div>
                  <div className={`w-12 h-7 rounded-full p-0.5 transition-colors ${
                    item.value ? "bg-primary" : "bg-muted"
                  }`}>
                    <motion.div
                      className="w-6 h-6 rounded-full bg-card shadow-sm"
                      animate={{ x: item.value ? 20 : 0 }}
                      transition={{ type: "spring", stiffness: 500, damping: 30 }}
                    />
                  </div>
                </button>
              ))}
            </div>
          )}

          {currentStep === 1 && !isHouse && (
            <div className="space-y-6 pt-6">
              <div className="text-center space-y-2 pb-4">
                <h2 className="text-[28px] font-bold text-foreground">Bütçen</h2>
                <p className="text-muted-foreground text-sm">Aylık kira bütçe aralığını belirle</p>
              </div>

              <div className="card-listing p-6 space-y-5">
                <div className="text-center">
                  <p className="text-2xl font-bold text-primary">
                    {budget[0].toLocaleString("tr-TR")} ₺ — {budget[1].toLocaleString("tr-TR")} ₺
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">Aylık Bütçe</p>
                </div>
                <Slider
                  value={budget}
                  onValueChange={setBudget}
                  min={1000}
                  max={20000}
                  step={500}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>1.000 ₺</span>
                  <span>20.000 ₺</span>
                </div>
              </div>
            </div>
          )}

          {/* Step 2: Location */}
          {currentStep === 2 && (
            <div className="space-y-5 pt-6">
              <div className="text-center space-y-2 pb-4">
                <h2 className="text-[28px] font-bold text-foreground">Konum</h2>
                <p className="text-muted-foreground text-sm">{isHouse ? "Evin hangi semtte?" : "Hangi semti tercih ediyorsun?"}</p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                {["Kadıköy", "Beşiktaş", "Üsküdar", "Şişli", "Bakırköy", "Beyoğlu", "Ataşehir", "Maltepe"].map(d => (
                  <button
                    key={d}
                    onClick={() => setDistrict(d)}
                    className={`p-4 rounded-2xl border-2 text-sm font-medium transition-all flex items-center gap-2 ${
                      district === d
                        ? "border-secondary bg-lavender/30 shadow-md"
                        : "border-border bg-card hover:border-primary/30 hover:shadow-sm"
                    }`}
                  >
                    <MapPin className={`w-4 h-4 ${district === d ? "text-primary" : "text-muted-foreground"}`} />
                    {d}
                  </button>
                ))}
              </div>

              {/* Ev ilanında ilçe seçilince adil fiyat danışmanını göster. */}
              {isHouse && district && (
                <FairPriceCheck
                  district={district}
                  askingPrice={rent ? Number(rent) : undefined}
                  roomCount={roomCount}
                />
              )}
            </div>
          )}

          {/* Step 3: Photos */}
          {currentStep === 3 && (
            <div className="space-y-5 pt-6">
              <div className="text-center space-y-2 pb-4">
                <h2 className="text-[28px] font-bold text-foreground">Fotoğraflar</h2>
                <p className="text-muted-foreground text-sm">
                  {isHouse ? "Evin fotoğraflarını ekle (en az 1)" : "Profil fotoğrafını ekle (en az 1)"}
                </p>
              </div>

              <div className="grid grid-cols-3 gap-3">
                {photos.map((photo, i) => (
                  <div key={i} className="aspect-square rounded-2xl overflow-hidden border-2 border-primary relative shadow-md group">
                    <img src={photo} alt="" className="w-full h-full object-cover" />
                    <div className="absolute top-2 right-2 w-6 h-6 rounded-full bg-accent flex items-center justify-center">
                      <Check className="w-4 h-4 text-accent-foreground" />
                    </div>
                    <button
                      onClick={() => removePhoto(i)}
                      className="absolute top-2 left-2 w-6 h-6 rounded-full bg-destructive/90 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <X className="w-3 h-3 text-destructive-foreground" />
                    </button>
                  </div>
                ))}
                {photos.length < 6 && (
                  <button
                    onClick={handlePhotoAdd}
                    className="aspect-square rounded-2xl border-2 border-dashed border-muted-foreground/30 flex flex-col items-center justify-center gap-2 bg-card hover:bg-lavender/20 transition-all hover:border-primary/40 hover:shadow-sm"
                  >
                    <ImagePlus className="w-8 h-8 text-muted-foreground" />
                    <span className="text-xs text-muted-foreground font-medium">Ekle</span>
                  </button>
                )}
              </div>
              <p className="text-xs text-muted-foreground text-center">{photos.length}/6 fotoğraf eklendi</p>
            </div>
          )}
        </motion.div>
      </AnimatePresence>

      {/* Bottom CTA */}
      <div className="fixed bottom-0 left-0 right-0 bg-card/80 backdrop-blur-lg p-6 pb-[max(1.5rem,env(safe-area-inset-bottom))]" style={{ boxShadow: '0 -1px 0 rgba(0,0,0,0.04)' }}>
        <Button
          onClick={next}
          disabled={!canProceed()}
          className="w-full h-14 text-base font-bold bg-gradient-to-r from-primary to-secondary text-primary-foreground hover:opacity-90 shadow-lg disabled:opacity-40"
        >
          {currentStep === totalSteps - 1 ? "İlanı Yayınla 🚀" : "Devam Et"}
          <ArrowRight className="w-5 h-5 ml-2" />
        </Button>
      </div>
    </div>
  );
};

export default CreateListing;
