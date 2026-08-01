import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import {
  ArrowLeft, ArrowRight, ArrowUpDown, Car, Check, Cigarette, Dog, FileText,
  Flame, Home, ImagePlus, MapPin, Sofa, Sun, Thermometer, User, Wifi, X
} from "lucide-react";
import { toast } from "@/hooks/use-toast";
import { useQueryClient } from "@tanstack/react-query";
import FairPriceCheck from "@/components/FairPriceCheck";
import AuthGate from "@/components/AuthGate";
import { useAuth } from "@/contexts/AuthContext";
import { ApiError, createListing, LISTING_FEATURES, type ListingFeature } from "@/lib/api";
import { usePhotoUpload } from "@/hooks/use-photo-upload";
import { useI18n } from "@/i18n";
import type { TranslationKey } from "@/i18n/translations";

type ListingType = "ev_ilani" | "kisisel_ilan" | null;

// Ev özellikleri — `value` backend sütun adıdır (FilterModal'daki çiplerle aynı
// anahtarlar), yalnızca etiket dile göre değişir.
const featureFields: { value: ListingFeature; key: TranslationKey; icon: typeof Sofa }[] = [
  { value: "furnished", key: "filter.furnished", icon: Sofa },
  { value: "elevator", key: "filter.elevator", icon: ArrowUpDown },
  { value: "parking", key: "filter.parking", icon: Car },
  { value: "internet_included", key: "filter.internet", icon: Wifi },
  { value: "heating_included", key: "filter.heating", icon: Thermometer },
  { value: "balcony", key: "filter.balcony", icon: Sun },
  { value: "natural_gas", key: "filter.gas", icon: Flame },
];

const emptyFeatures = (): Record<ListingFeature, boolean> =>
  Object.fromEntries(LISTING_FEATURES.map(k => [k, false])) as Record<ListingFeature, boolean>;

const CreateListing = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { isLoggedIn } = useAuth();
  const { t, n } = useI18n();

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
  const [features, setFeatures] = useState<Record<ListingFeature, boolean>>(emptyFeatures);

  // Kişisel ilan fields
  const [budget, setBudget] = useState([4000, 8000]);

  const [submitting, setSubmitting] = useState(false);
  // Son gönderim hatası — toast kaybolduktan sonra da formda görünür kalsın.
  const [submitError, setSubmitError] = useState<{ message: string; moderation: boolean } | null>(null);

  const isHouse = listingType === "ev_ilani";

  // Her iki ilan tipi de 4 adım: Detaylar → (Kurallar | Bütçe) → Konum → Fotoğraflar
  const totalSteps = 4;
  const progress = ((currentStep + 1) / totalSteps) * 100;

  const { pick: pickPhoto, uploading } = usePhotoUpload(url =>
    setPhotos(prev => (prev.length < 6 ? [...prev, url] : prev)),
  );

  const removePhoto = (index: number) => {
    setPhotos(photos.filter((_, i) => i !== index));
  };

  const toggleFeature = (key: ListingFeature) =>
    setFeatures(prev => ({ ...prev, [key]: !prev[key] }));

  const canProceed = () => {
    if (currentStep === 0) return title.length > 0 && description.length > 0 && (isHouse ? rent && roomCount : true);
    if (currentStep === 1) return true;
    if (currentStep === 2) return district !== "";
    if (currentStep === 3) return photos.length >= 1;
    return false;
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setSubmitError(null);
    try {
      // Ev ilanında 7 özelliğin HEPSİ açıkça gönderilir: işaretlenmeyen alan
      // false yazılır. Eskiden yalnızca işaretliler gönderiliyordu, bu yüzden
      // veritabanına hiç false düşmüyor ve "bilinmiyor" (null) ile "yok"
      // ayrımı pratikte kayboluyordu. Kişisel ilanda hiç gönderilmez —
      // ev arayan kişinin asansörü/otoparkı olmaz, orada alanlar null kalır.
      const houseFeatures = Object.fromEntries(
        LISTING_FEATURES.map(key => [key, features[key] === true]),
      ) as Record<ListingFeature, boolean>;

      await createListing({
        type: listingType!,
        title,
        description,
        district,
        photos,
        ...(isHouse
          ? {
              rent: Number(rent),
              room_count: roomCount,
              smoking_allowed: smokingAllowed,
              pets_allowed: petsAllowed,
              ...houseFeatures,
            }
          : { budget_min: budget[0], budget_max: budget[1] }),
      });
      queryClient.invalidateQueries({ queryKey: ["listings"] });
      toast({
        title: t("create.successTitle"),
        description: t("create.successDesc", { title }),
      });
      navigate("/listings");
    } catch (err) {
      // 422 = sunucudaki içerik denetimi reddetti; mesaj kullanıcıya ne
      // yapması gerektiğini söylüyor, olduğu gibi gösterilir.
      const moderation = err instanceof ApiError && err.status === 422;
      const message = err instanceof Error ? err.message : t("create.failedDesc");
      setSubmitError({ message, moderation });
      toast({
        title: moderation ? t("create.moderationTitle") : t("create.failedTitle"),
        description: message,
        variant: "destructive",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const next = () => {
    if (currentStep === totalSteps - 1) {
      handleSubmit();
    } else {
      setCurrentStep(s => s + 1);
    }
  };

  const back = () => {
    setSubmitError(null);
    if (currentStep > 0) {
      setCurrentStep(s => s - 1);
    } else {
      setListingType(null);
    }
  };

  // İlan vermek giriş ister — form doldurulup son adımda 401 yemesin
  if (!isLoggedIn) {
    return (
      <div className="min-h-screen bg-background">
        <AuthGate show onClose={() => navigate(-1)} />
      </div>
    );
  }

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
          <h1 className="font-bold text-xl text-foreground">{t("create.title")}</h1>
        </div>

        <div className="flex-1 px-6 pt-8 space-y-6">
          <div className="text-center space-y-3">
            <div className="w-16 h-16 rounded-2xl bg-lavender/50 flex items-center justify-center mx-auto">
              <FileText className="w-8 h-8 text-primary" />
            </div>
            <h2 className="text-[28px] font-bold text-foreground">{t("create.typeQuestion")}</h2>
            <p className="text-muted-foreground text-sm max-w-[280px] mx-auto">
              {t("create.typeSub")}
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
                <h3 className="font-bold text-lg text-foreground">{t("common.houseListing")}</h3>
                <p className="text-sm text-muted-foreground mt-1">{t("create.houseDesc")}</p>
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
                <h3 className="font-bold text-lg text-foreground">{t("common.personalListing")}</h3>
                <p className="text-sm text-muted-foreground mt-1">{t("create.personalDesc")}</p>
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
            {isHouse ? `🏠 ${t("common.houseListing")}` : `👤 ${t("common.personalListing")}`}
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
                <h2 className="text-[28px] font-bold text-foreground">{t("create.detailsTitle")}</h2>
                <p className="text-muted-foreground text-sm">{t("create.detailsSub")}</p>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">{t("create.titleLabel")}</label>
                <Input
                  placeholder={isHouse ? t("create.titlePlaceholderHouse") : t("create.titlePlaceholderPersonal")}
                  value={title}
                  onChange={e => setTitle(e.target.value)}
                  className="h-14 text-base rounded-2xl bg-card border-border shadow-sm focus:shadow-md focus:ring-2 focus:ring-primary/20 transition-shadow"
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">{t("create.descLabel")}</label>
                <textarea
                  placeholder={t("create.descPlaceholder")}
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                  rows={4}
                  className="w-full rounded-2xl bg-card border border-border px-4 py-3 text-base text-foreground placeholder:text-muted-foreground shadow-sm focus:shadow-md focus:ring-2 focus:ring-primary/20 transition-shadow outline-none resize-none"
                />
              </div>

              {isHouse && (
                <>
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-foreground">{t("create.rentLabel")}</label>
                    <Input
                      type="number"
                      placeholder={t("create.rentPlaceholder")}
                      value={rent}
                      onChange={e => setRent(e.target.value)}
                      className="h-14 text-base rounded-2xl bg-card border-border shadow-sm focus:shadow-md focus:ring-2 focus:ring-primary/20 transition-shadow"
                    />
                  </div>
                  <div className="space-y-3">
                    <label className="text-sm font-medium text-foreground">{t("create.roomsLabel")}</label>
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

          {/* Step 1: Rules + features (ev) or Budget (kişisel) */}
          {currentStep === 1 && isHouse && (
            <div className="space-y-5 pt-6">
              <div className="text-center space-y-2 pb-4">
                <h2 className="text-[28px] font-bold text-foreground">{t("create.rulesTitle")}</h2>
                <p className="text-muted-foreground text-sm">{t("create.rulesSub")}</p>
              </div>

              {[
                { key: "smoking", icon: Cigarette, label: t("create.smokingLabel"), desc: t("create.smokingDesc"), value: smokingAllowed, setValue: setSmokingAllowed },
                { key: "pets", icon: Dog, label: t("create.petsLabel"), desc: t("create.petsDesc"), value: petsAllowed, setValue: setPetsAllowed },
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

              {/* Ev özellikleri — yalnızca ev ilanında; işaretlenenler filtrelerde kullanılıyor */}
              <div className="pt-2 space-y-3">
                <div>
                  <h3 className="text-sm font-medium text-foreground">{t("create.featuresTitle")}</h3>
                  <p className="text-xs text-muted-foreground mt-1">{t("create.featuresSub")}</p>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  {featureFields.map(f => {
                    const selected = features[f.value];
                    return (
                      <button
                        key={f.value}
                        onClick={() => toggleFeature(f.value)}
                        className={`p-4 rounded-2xl border-2 text-sm font-medium transition-all flex items-center gap-2 text-left ${
                          selected
                            ? "border-secondary bg-lavender/30 shadow-md"
                            : "border-border bg-card hover:border-primary/30 hover:shadow-sm"
                        }`}
                      >
                        <f.icon className={`w-4 h-4 flex-shrink-0 ${selected ? "text-primary" : "text-muted-foreground"}`} />
                        <span className="leading-tight">{t(f.key)}</span>
                        {selected && <Check className="w-4 h-4 text-primary ml-auto flex-shrink-0" />}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {currentStep === 1 && !isHouse && (
            <div className="space-y-6 pt-6">
              <div className="text-center space-y-2 pb-4">
                <h2 className="text-[28px] font-bold text-foreground">{t("create.budgetTitle")}</h2>
                <p className="text-muted-foreground text-sm">{t("create.budgetSub")}</p>
              </div>

              <div className="card-listing p-6 space-y-5">
                <div className="text-center">
                  <p className="text-2xl font-bold text-primary">
                    {n(budget[0])} {t("common.currency")} — {n(budget[1])} {t("common.currency")}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">{t("create.budgetLabel")}</p>
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
                  <span>{n(1000)} {t("common.currency")}</span>
                  <span>{n(20000)} {t("common.currency")}</span>
                </div>
              </div>
            </div>
          )}

          {/* Step 2: Location */}
          {currentStep === 2 && (
            <div className="space-y-5 pt-6">
              <div className="text-center space-y-2 pb-4">
                <h2 className="text-[28px] font-bold text-foreground">{t("create.locationTitle")}</h2>
                <p className="text-muted-foreground text-sm">
                  {isHouse ? t("create.locationSubHouse") : t("create.locationSubPersonal")}
                </p>
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
                <h2 className="text-[28px] font-bold text-foreground">{t("create.photosTitle")}</h2>
                <p className="text-muted-foreground text-sm">
                  {isHouse ? t("create.photosSubHouse") : t("create.photosSubPersonal")}
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
                    onClick={pickPhoto}
                    disabled={uploading}
                    className="aspect-square rounded-2xl border-2 border-dashed border-muted-foreground/30 flex flex-col items-center justify-center gap-2 bg-card hover:bg-lavender/20 transition-all hover:border-primary/40 hover:shadow-sm disabled:opacity-50"
                  >
                    <ImagePlus className={`w-8 h-8 text-muted-foreground ${uploading ? "animate-pulse" : ""}`} />
                    <span className="text-xs text-muted-foreground font-medium">
                      {uploading ? t("common.loading") : t("create.addPhoto")}
                    </span>
                  </button>
                )}
              </div>
              <p className="text-xs text-muted-foreground text-center">
                {t("create.photoCount", { count: photos.length })}
              </p>
            </div>
          )}
        </motion.div>
      </AnimatePresence>

      {/* Bottom CTA */}
      <div className="fixed bottom-0 left-0 right-0 bg-card/80 backdrop-blur-lg p-6 pb-[max(1.5rem,env(safe-area-inset-bottom))]" style={{ boxShadow: '0 -1px 0 rgba(0,0,0,0.04)' }}>
        {/* Gönderim hatası formu kapatmaz; sunucunun açıklaması burada kalır. */}
        {submitError && (
          <div className="mb-3 rounded-2xl border border-destructive/40 bg-destructive/10 px-4 py-3 space-y-2">
            <p className="text-xs font-semibold text-foreground">
              {submitError.moderation ? t("create.moderationTitle") : t("create.failedTitle")}
            </p>
            <p className="text-xs text-muted-foreground leading-relaxed">{submitError.message}</p>
            {submitError.moderation && (
              <button
                onClick={() => { setSubmitError(null); setCurrentStep(0); }}
                className="text-xs font-semibold text-primary hover:underline"
              >
                {t("create.editTexts")}
              </button>
            )}
          </div>
        )}
        <Button
          onClick={next}
          disabled={!canProceed() || submitting}
          className="w-full h-14 text-base font-bold bg-gradient-to-r from-primary to-secondary text-primary-foreground hover:opacity-90 shadow-lg disabled:opacity-40"
        >
          {submitting ? t("create.publishing") : currentStep === totalSteps - 1 ? t("create.publish") : t("common.continue")}
          <ArrowRight className="w-5 h-5 ml-2" />
        </Button>
      </div>
    </div>
  );
};

export default CreateListing;
