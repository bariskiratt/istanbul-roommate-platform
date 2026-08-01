import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import {
  ArrowLeft, ArrowRight, ArrowUpDown, Car, Check, Cigarette, Dog, FileText,
  Flame, Home, ImagePlus, Sofa, Sun, Thermometer, User, Wifi, X
} from "lucide-react";
import { toast } from "@/hooks/use-toast";
import { useQueryClient } from "@tanstack/react-query";
import FairPriceCheck from "@/components/FairPriceCheck";
import LocationPicker, { type LocationValue } from "@/components/LocationPicker";
import AuthGate from "@/components/AuthGate";
import { useAuth } from "@/contexts/AuthContext";
import {
  ApiError, createListing, LISTING_FEATURES,
  type ListingFeature, type ListingPayload,
} from "@/lib/api";
import { usePhotoUpload } from "@/hooks/use-photo-upload";
import { useI18n } from "@/i18n";
import type { TranslationKey } from "@/i18n/translations";

type ListingType = "ev_ilani" | "kisisel_ilan" | null;

// Sunucu ilanı en az 3, en çok 6 fotoğrafla kabul ediyor (POST /api/listings).
const MIN_PHOTOS = 3;
const MAX_PHOTOS = 6;

/**
 * Sunucunun bildirdiği hatalı alan hangi adımda düzeltilir. Denetim reddi
 * "title"/"description" döndürür (ikisi de 0. adımda), doğrulama hatası ise
 * alan adını (ör. "photos") verir. Burada olmayan bir alan gelirse kullanıcı
 * bulunduğu adımda kalır, hata yine de metinle gösterilir.
 */
const STEP_OF_FIELD: Record<string, number> = { title: 0, description: 0, photos: 3 };

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

/** Formun o anki hâli — gönderilecek gövdenin tek girdisi. */
export interface ListingDraft {
  listingType: Exclude<ListingType, null>;
  title: string;
  description: string;
  location: LocationValue;
  photos: string[];
  rent: string;
  roomCount: string;
  smokingAllowed: boolean;
  petsAllowed: boolean;
  features: Record<ListingFeature, boolean>;
  budget: number[];
}

/**
 * Form durumundan `POST /api/listings` gövdesini kurar. Saf fonksiyondur —
 * bileşenden ayrı test edilebilsin diye dışa açılır.
 *
 * Tipe özgü alanlar KESİNLİKLE kendi dalında kalır. Kullanıcı adımlar arasında
 * ileri/geri gidebildiği ve en baştan ilan tipini değiştirebildiği için form
 * durumu iki tip arasında korunur; ortak dalda bırakılan bir alan, artık
 * gösterilmeyen bir değeri sessizce kaydederdi (bkz. `neighborhood`).
 */
export const buildListingPayload = (draft: ListingDraft): ListingPayload => {
  const isHouse = draft.listingType === "ev_ilani";
  const { district, neighborhood } = draft.location;

  if (!isHouse) {
    // Kişisel ilan: mahalle 2. adımda hiç sorulmaz (districtOnly), ev
    // özellikleri de ev arayan kişide olamaz — ikisi de gönderilmez.
    return {
      type: draft.listingType,
      title: draft.title,
      description: draft.description,
      district,
      photos: draft.photos,
      budget_min: draft.budget[0],
      budget_max: draft.budget[1],
    };
  }

  // Ev ilanında 7 özelliğin HEPSİ açıkça gönderilir: işaretlenmeyen alan false
  // yazılır. Eskiden yalnızca işaretliler gönderiliyordu, bu yüzden
  // veritabanına hiç false düşmüyor ve "bilinmiyor" (null) ile "yok" ayrımı
  // pratikte kayboluyordu.
  const houseFeatures = Object.fromEntries(
    LISTING_FEATURES.map(key => [key, draft.features[key] === true]),
  ) as Record<ListingFeature, boolean>;

  return {
    type: draft.listingType,
    title: draft.title,
    description: draft.description,
    district,
    // Boş dize gönderilmez: mahalle seçilmediyse alan hiç yollanmaz.
    ...(neighborhood ? { neighborhood } : {}),
    photos: draft.photos,
    rent: Number(draft.rent),
    room_count: draft.roomCount,
    smoking_allowed: draft.smokingAllowed,
    pets_allowed: draft.petsAllowed,
    ...houseFeatures,
  };
};

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
  // İlçe zorunlu, mahalle isteğe bağlı; ikisi birlikte tutulur ki ilçe
  // değişince başka ilçenin mahallesi geride kalmasın (bkz. LocationPicker).
  const [location, setLocation] = useState<LocationValue>({ district: "", neighborhood: "" });
  const { district, neighborhood } = location;
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
  // `field` doluysa hata o alanın ALTINDA gösterilir ve alan işaretlenir.
  const [submitError, setSubmitError] = useState<
    { message: string; moderation: boolean; field: string | null } | null
  >(null);

  const isHouse = listingType === "ev_ilani";

  // Her iki ilan tipi de 4 adım: Detaylar → (Kurallar | Bütçe) → Konum → Fotoğraflar
  const totalSteps = 4;
  const progress = ((currentStep + 1) / totalSteps) * 100;

  const {
    pick: pickPhoto,
    uploading,
    error: uploadError,
    clearError: clearUploadError,
  } = usePhotoUpload(url => {
    setPhotos(prev => (prev.length < MAX_PHOTOS ? [...prev, url] : prev));
    clearFieldError("photos");
  });

  const removePhoto = (index: number) => {
    setPhotos(photos.filter((_, i) => i !== index));
    clearUploadError();
  };

  /**
   * Kullanıcı hatalı alana dokununca işareti kaldırır. Yalnızca o alanın
   * hatasını siler; başka bir alandan gelen uyarı yerinde kalır.
   */
  function clearFieldError(field: string) {
    setSubmitError(prev => (prev?.field === field ? null : prev));
  }

  const toggleFeature = (key: ListingFeature) =>
    setFeatures(prev => ({ ...prev, [key]: !prev[key] }));

  const canProceed = () => {
    if (currentStep === 0) return title.length > 0 && description.length > 0 && (isHouse ? rent && roomCount : true);
    if (currentStep === 1) return true;
    if (currentStep === 2) return district !== "";
    // Sunucu 3'ten az fotoğrafı reddediyor; kullanıcı son adımda 422 yemesin.
    if (currentStep === 3) return photos.length >= MIN_PHOTOS;
    return false;
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setSubmitError(null);
    try {
      await createListing(
        buildListingPayload({
          listingType: listingType!,
          title,
          description,
          location,
          photos,
          rent,
          roomCount,
          smokingAllowed,
          petsAllowed,
          features,
          budget,
        }),
      );
      queryClient.invalidateQueries({ queryKey: ["listings"] });
      toast({
        title: t("create.successTitle"),
        description: t("create.successDesc", { title }),
      });
      navigate("/listings");
    } catch (err) {
      const apiError = err instanceof ApiError ? err : null;
      // Denetim reddi alan bazlı gelir ve gerekçe kodları taşır; Pydantic
      // doğrulama hatası da 422'dir ama gerekçe listesi boştur. Ayrımı
      // gerekçelerden yapıyoruz — başlık metni yanlış olmasın.
      const moderation = apiError?.status === 422 && apiError.reasons.length > 0;
      const field = apiError?.field ?? null;
      // Sunucunun fotoğraf doğrulama metni İngilizce ve teknik ("List should
      // have at least 3 items…"); eksik fotoğraf durumunu kendi dilimizde
      // anlatıyoruz. Başka bir fotoğraf hatasında sunucunun metni korunur.
      const message =
        field === "photos" && photos.length < MIN_PHOTOS
          ? t("create.photoMinError", { min: MIN_PHOTOS })
          : err instanceof Error
            ? err.message
            : t("create.failedDesc");
      setSubmitError({ message, moderation, field });
      // Hatalı alan biliniyorsa kullanıcıyı oraya götür — yazdıkları duruyor.
      const step = field ? STEP_OF_FIELD[field] : undefined;
      if (step !== undefined) setCurrentStep(step);
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

  // Hatanın işaretlediği alanlar; hata metni doğrudan alanın altında çıkar.
  const titleRejected = submitError?.field === "title";
  const descRejected = submitError?.field === "description";
  const photosRejected = submitError?.field === "photos";
  // Hata metni ilgili adımda alanın altında görünüyorsa alttaki kutuda
  // TEKRARLANMAZ; kutuda yalnızca başlık kalır.
  const inlineField =
    submitError?.field && submitError.field in STEP_OF_FIELD ? submitError.field : null;
  const shownInline = inlineField !== null && STEP_OF_FIELD[inlineField] === currentStep;
  // Alan bilinmiyorsa denetim reddi yine de metinlerin olduğu adıma yönlendirir.
  const errorStep = inlineField
    ? STEP_OF_FIELD[inlineField]
    : submitError?.moderation
      ? 0
      : undefined;

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
                <label htmlFor="listing-title" className="text-sm font-medium text-foreground">
                  {t("create.titleLabel")}
                </label>
                <Input
                  id="listing-title"
                  placeholder={isHouse ? t("create.titlePlaceholderHouse") : t("create.titlePlaceholderPersonal")}
                  value={title}
                  onChange={e => { setTitle(e.target.value); clearFieldError("title"); }}
                  aria-invalid={titleRejected}
                  aria-describedby={titleRejected ? "listing-title-error" : undefined}
                  className={`h-14 text-base rounded-2xl bg-card shadow-sm focus:shadow-md transition-shadow ${
                    titleRejected
                      ? "border-2 border-destructive focus:ring-2 focus:ring-destructive/25"
                      : "border-border focus:ring-2 focus:ring-primary/20"
                  }`}
                />
                {titleRejected && (
                  <p id="listing-title-error" role="alert" className="text-xs text-destructive leading-relaxed">
                    {submitError.message}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <label htmlFor="listing-desc" className="text-sm font-medium text-foreground">
                  {t("create.descLabel")}
                </label>
                <textarea
                  id="listing-desc"
                  placeholder={t("create.descPlaceholder")}
                  value={description}
                  onChange={e => { setDescription(e.target.value); clearFieldError("description"); }}
                  rows={4}
                  aria-invalid={descRejected}
                  aria-describedby={descRejected ? "listing-desc-error" : undefined}
                  className={`w-full rounded-2xl bg-card px-4 py-3 text-base text-foreground placeholder:text-muted-foreground shadow-sm focus:shadow-md transition-shadow outline-none resize-none ${
                    descRejected
                      ? "border-2 border-destructive focus:ring-2 focus:ring-destructive/25"
                      : "border border-border focus:ring-2 focus:ring-primary/20"
                  }`}
                />
                {descRejected && (
                  <p id="listing-desc-error" role="alert" className="text-xs text-destructive leading-relaxed">
                    {submitError.message}
                  </p>
                )}
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

              {/* İlçe/mahalle listesi sunucudan gelir (38 ilçe, 539 mahalle).
                  Mahalle YALNIZCA ev ilanında sorulur: adil fiyat sadece ev
                  ilanları için hesaplanıyor, kişisel ilanda mahallenin bir
                  karşılığı olmazdı. */}
              <LocationPicker value={location} onChange={setLocation} districtOnly={!isHouse} />

              {/* Ev ilanında ilçe seçilince adil fiyat danışmanını göster. */}
              {isHouse && district && (
                <FairPriceCheck
                  district={district}
                  neighborhood={neighborhood}
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
                {photos.length < MAX_PHOTOS && (
                  <button
                    onClick={() => pickPhoto(MAX_PHOTOS - photos.length)}
                    disabled={uploading}
                    className={`aspect-square rounded-2xl border-2 border-dashed flex flex-col items-center justify-center gap-2 bg-card hover:bg-lavender/20 transition-all hover:border-primary/40 hover:shadow-sm disabled:opacity-50 ${
                      photosRejected ? "border-destructive" : "border-muted-foreground/30"
                    }`}
                  >
                    <ImagePlus className={`w-8 h-8 text-muted-foreground ${uploading ? "animate-pulse" : ""}`} />
                    <span className="text-xs text-muted-foreground font-medium">
                      {uploading ? t("common.loading") : t("create.addPhoto")}
                    </span>
                  </button>
                )}
              </div>

              {/* Dolu her kutucuk bir fotoğraf. Kutucuk sayısı ÜST sınırdır:
                  alt sınır kadar (3) gösterilseydi sayaç 2/3'ten 3/6'ya
                  atlıyor ve çubuk üçüncüden sonra dolmayı bırakıyordu.
                  Alt sınıra kadar olanlar zorunlu, sonrası isteğe bağlı. */}
              <div className="space-y-2">
                <div className="flex items-center justify-center gap-1.5" aria-hidden="true">
                  {Array.from({ length: MAX_PHOTOS }).map((_, i) => (
                    <span
                      key={i}
                      className={`h-1.5 w-6 rounded-full transition-colors ${
                        i < photos.length
                          ? "bg-primary"
                          : i < MIN_PHOTOS
                            ? "bg-muted"
                            : "bg-muted/50"
                      }`}
                    />
                  ))}
                </div>
                <p className="text-xs font-semibold text-foreground text-center" aria-live="polite">
                  {t("create.photoCount", { count: photos.length, max: MAX_PHOTOS })}
                </p>
                <p className="text-xs text-muted-foreground text-center leading-relaxed">
                  {photos.length < MIN_PHOTOS
                    ? t("create.photoMinHint", { min: MIN_PHOTOS })
                    : t("create.photoEnough", { max: MAX_PHOTOS })}
                </p>
              </div>

              {/* Sunucu fotoğrafları reddettiyse (ör. 3'ten az) burada söylenir. */}
              {photosRejected && (
                <p role="alert" className="text-xs text-destructive text-center leading-relaxed">
                  {submitError.message}
                </p>
              )}

              {/* Yükleme hatası kullanıcıyı kilitlemez: metin kalır, yeniden
                  denemek için düğme hemen altındadır. */}
              {uploadError && (
                <div
                  role="alert"
                  className="rounded-2xl border border-destructive/40 bg-destructive/10 px-4 py-3 space-y-2"
                >
                  <p className="text-xs font-semibold text-foreground">{t("common.photoUploadFailed")}</p>
                  <p className="text-xs text-muted-foreground leading-relaxed">{uploadError}</p>
                  {photos.length < MAX_PHOTOS && (
                    <button
                      onClick={() => pickPhoto(MAX_PHOTOS - photos.length)}
                      disabled={uploading}
                      className="text-xs font-semibold text-primary hover:underline disabled:opacity-50"
                    >
                      {t("common.retry")}
                    </button>
                  )}
                </div>
              )}
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
            {/* Metin ilgili adımda alanın altında duruyorsa burada tekrarlanmaz. */}
            {!shownInline && (
              <p className="text-xs text-muted-foreground leading-relaxed">{submitError.message}</p>
            )}
            {!shownInline && errorStep !== undefined && (
              <button
                onClick={() => setCurrentStep(errorStep)}
                className="text-xs font-semibold text-primary hover:underline"
              >
                {errorStep === 3 ? t("create.goToPhotos") : t("create.editTexts")}
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
