import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import {
  ArrowLeft, ArrowUpDown, Car, Check, Cigarette, Dog,
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
      // /listings yalnızca yöneticiye açık; öğrenci orada "Bu sayfa şu an
      // kapalı" görüyordu. Yeni ilanı "İlanlarım" sekmesinde gösteriyoruz.
      navigate("/profile", { state: { tab: "listings" } });
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

  // Seçili seçenek: mürekkeple doldurulmuş kutu (Onboarding ile aynı dil)
  const choice = (selected: boolean) =>
    selected
      ? "border-foreground bg-foreground text-background"
      : "border-input bg-card text-foreground hover:border-foreground/40";

  // Type selection screen
  if (!listingType) {
    return (
      <div className="min-h-screen bg-background flex flex-col">
        <div className="px-4 h-16 flex items-center gap-2 border-b border-border">
          <button
            onClick={() => navigate(-1)}
            aria-label={t("common.back")}
            className="w-10 h-10 rounded-full flex items-center justify-center text-foreground hover:bg-muted transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h1 className="font-display text-[1.35rem] font-semibold text-foreground">{t("create.title")}</h1>
        </div>

        <div className="flex-1 w-full max-w-md mx-auto px-5 pt-8 pb-12">
          <h2 className="text-[2.1rem] text-foreground leading-[1.08]">{t("create.typeQuestion")}</h2>
          <p className="mt-2 text-muted-foreground leading-relaxed">{t("create.typeSub")}</p>

          <div className="mt-8 space-y-3">
            {[
              { type: "ev_ilani" as const, icon: Home, label: t("common.houseListing"), desc: t("create.houseDesc") },
              { type: "kisisel_ilan" as const, icon: User, label: t("common.personalListing"), desc: t("create.personalDesc") },
            ].map(opt => (
              <button
                key={opt.type}
                onClick={() => { setListingType(opt.type); setCurrentStep(0); }}
                className="w-full rounded-2xl border border-border bg-card p-5 flex items-start gap-4 text-left hover:border-foreground/40 transition-colors"
              >
                <opt.icon className="w-6 h-6 mt-1 shrink-0 text-secondary" />
                <span className="min-w-0">
                  <span className="block font-display text-xl font-semibold text-foreground">{opt.label}</span>
                  <span className="block mt-1 text-[14px] text-muted-foreground leading-relaxed">{opt.desc}</span>
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Üst çubuk: geri, adım sayacı, ilan tipi */}
      <div className="px-4 h-16 flex items-center gap-2 border-b border-border">
        <button
          onClick={back}
          aria-label={t("common.back")}
          className="w-10 h-10 rounded-full flex items-center justify-center text-foreground hover:bg-muted transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <span className="flex-1 text-[13px] text-muted-foreground text-center">
          {t("ob.stepCounter", { current: currentStep + 1, total: totalSteps })}
        </span>
        <span className="h-8 px-3 rounded-full border border-border text-[12px] font-semibold text-foreground flex items-center">
          {isHouse ? t("common.houseListing") : t("common.personalListing")}
        </span>
      </div>

      {/* İlerleme: mürekkep çizgisi */}
      <div className="h-[3px] w-full bg-muted">
        <motion.div
          className="h-full bg-foreground"
          initial={false}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.4, ease: "easeOut" }}
        />
      </div>

      {/* Content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={currentStep}
          initial={{ opacity: 0, x: 24 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -24 }}
          transition={{ duration: 0.25 }}
          className="flex-1 w-full max-w-md mx-auto px-5 pb-40 overflow-y-auto"
        >
          {/* Step 0: Details */}
          {currentStep === 0 && (
            <div className="space-y-5">
              <StepHeader title={t("create.detailsTitle")} sub={t("create.detailsSub")} />

              <div className="space-y-2">
                <label htmlFor="listing-title" className="text-sm font-semibold text-foreground">
                  {t("create.titleLabel")}
                </label>
                <Input
                  id="listing-title"
                  placeholder={isHouse ? t("create.titlePlaceholderHouse") : t("create.titlePlaceholderPersonal")}
                  value={title}
                  onChange={e => { setTitle(e.target.value); clearFieldError("title"); }}
                  aria-invalid={titleRejected}
                  aria-describedby={titleRejected ? "listing-title-error" : undefined}
                  className={`h-12 ${titleRejected ? "border-destructive focus-visible:border-destructive focus-visible:ring-destructive/20" : ""}`}
                />
                {titleRejected && (
                  <p id="listing-title-error" role="alert" className="text-[13px] text-destructive leading-relaxed">
                    {submitError.message}
                  </p>
                )}
              </div>

              {/* Açıklama kişinin kendi sözü: ilanda nasıl görünecekse
                  (çizgili kâğıt) öyle yazılır. */}
              <div className="space-y-2">
                <label htmlFor="listing-desc" className="text-sm font-semibold text-foreground">
                  {t("create.descLabel")}
                </label>
                <textarea
                  id="listing-desc"
                  placeholder={t("create.descPlaceholder")}
                  value={description}
                  onChange={e => { setDescription(e.target.value); clearFieldError("description"); }}
                  rows={5}
                  aria-invalid={descRejected}
                  aria-describedby={descRejected ? "listing-desc-error" : undefined}
                  style={{ backgroundAttachment: "local" }}
                  className={`paper-ruled w-full rounded-xl border text-[15px] text-foreground placeholder:text-muted-foreground/80 outline-none resize-none transition-colors focus-visible:ring-[3px] ${
                    descRejected
                      ? "border-destructive focus-visible:ring-destructive/20"
                      : "border-input hover:border-foreground/30 focus-visible:border-secondary focus-visible:ring-secondary/20"
                  }`}
                />
                {descRejected && (
                  <p id="listing-desc-error" role="alert" className="text-[13px] text-destructive leading-relaxed">
                    {submitError.message}
                  </p>
                )}
              </div>

              {isHouse && (
                <>
                  <div className="space-y-2">
                    <label htmlFor="listing-rent" className="text-sm font-semibold text-foreground">{t("create.rentLabel")}</label>
                    <Input
                      id="listing-rent"
                      type="number"
                      inputMode="numeric"
                      placeholder={t("create.rentPlaceholder")}
                      value={rent}
                      onChange={e => setRent(e.target.value)}
                      className="h-12"
                    />
                  </div>
                  <div className="space-y-2">
                    <p className="text-sm font-semibold text-foreground">{t("create.roomsLabel")}</p>
                    <div className="grid grid-cols-4 gap-2">
                      {["1+0", "1+1", "2+1", "3+1"].map(r => (
                        <button
                          key={r}
                          onClick={() => setRoomCount(r)}
                          aria-pressed={roomCount === r}
                          className={`h-12 rounded-xl border text-[15px] font-semibold transition-colors ${choice(roomCount === r)}`}
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
            <div className="space-y-6">
              <StepHeader title={t("create.rulesTitle")} sub={t("create.rulesSub")} />

              <div className="rounded-2xl border border-border divide-y divide-border">
                {[
                  { key: "smoking", icon: Cigarette, label: t("create.smokingLabel"), desc: t("create.smokingDesc"), value: smokingAllowed, setValue: setSmokingAllowed },
                  { key: "pets", icon: Dog, label: t("create.petsLabel"), desc: t("create.petsDesc"), value: petsAllowed, setValue: setPetsAllowed },
                ].map(item => (
                  <button
                    key={item.key}
                    role="switch"
                    aria-checked={item.value}
                    onClick={() => item.setValue(!item.value)}
                    className="w-full flex items-center gap-4 px-4 py-4 text-left"
                  >
                    <item.icon className="w-5 h-5 shrink-0 text-muted-foreground" />
                    <span className="flex-1 min-w-0">
                      <span className="block font-semibold text-foreground">{item.label}</span>
                      <span className="block text-[13px] text-muted-foreground">{item.desc}</span>
                    </span>
                    <span className={`w-11 h-6 shrink-0 rounded-full p-0.5 transition-colors ${item.value ? "bg-foreground" : "bg-muted"}`}>
                      <motion.span
                        className="block w-5 h-5 rounded-full bg-card"
                        animate={{ x: item.value ? 20 : 0 }}
                        transition={{ type: "spring", stiffness: 500, damping: 30 }}
                      />
                    </span>
                  </button>
                ))}
              </div>

              {/* Ev özellikleri — yalnızca ev ilanında; işaretlenenler filtrelerde kullanılıyor */}
              <div className="space-y-3">
                <div>
                  <h3 className="text-xl text-foreground">{t("create.featuresTitle")}</h3>
                  <p className="text-[13px] text-muted-foreground mt-1 leading-relaxed">{t("create.featuresSub")}</p>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {featureFields.map(f => {
                    const selected = features[f.value];
                    return (
                      <button
                        key={f.value}
                        onClick={() => toggleFeature(f.value)}
                        aria-pressed={selected}
                        className={`min-h-[3.25rem] px-3.5 py-2.5 rounded-xl border text-[14px] font-semibold transition-colors flex items-center gap-2 text-left ${choice(selected)}`}
                      >
                        <f.icon className={`w-4 h-4 shrink-0 ${selected ? "" : "text-muted-foreground"}`} />
                        <span className="leading-tight">{t(f.key)}</span>
                        {selected && <Check className="w-4 h-4 ml-auto shrink-0" />}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {currentStep === 1 && !isHouse && (
            <div className="space-y-6">
              <StepHeader title={t("create.budgetTitle")} sub={t("create.budgetSub")} />

              <div className="rounded-2xl border border-border p-5 space-y-5">
                <div>
                  <p className="text-sm text-muted-foreground mb-1.5">{t("create.budgetLabel")}</p>
                  <p className="text-2xl font-semibold">
                    <span className="marker">{n(budget[0])}–{n(budget[1])} TL</span>
                  </p>
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
                  <span>{n(1000)} TL</span>
                  <span>{n(20000)} TL</span>
                </div>
              </div>
            </div>
          )}

          {/* Step 2: Location */}
          {currentStep === 2 && (
            <div className="space-y-5">
              <StepHeader
                title={t("create.locationTitle")}
                sub={isHouse ? t("create.locationSubHouse") : t("create.locationSubPersonal")}
              />

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
            <div className="space-y-5">
              <StepHeader
                title={t("create.photosTitle")}
                sub={isHouse ? t("create.photosSubHouse") : t("create.photosSubPersonal")}
              />

              <div className="grid grid-cols-3 gap-2">
                {photos.map((photo, i) => (
                  <div key={i} className="aspect-[3/4] rounded-xl overflow-hidden bg-muted relative">
                    <img src={photo} alt="" className="w-full h-full object-cover" />
                    {/* Dokunmatik ekranda üzerine gelme yok: kaldır düğmesi hep görünür */}
                    <button
                      onClick={() => removePhoto(i)}
                      aria-label={t("pedit.removePhoto")}
                      className="absolute top-1.5 right-1.5 w-7 h-7 rounded-full bg-background/90 text-foreground flex items-center justify-center hover:bg-background transition-colors"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
                {photos.length < MAX_PHOTOS && (
                  <button
                    onClick={() => pickPhoto(MAX_PHOTOS - photos.length)}
                    disabled={uploading}
                    className={`aspect-[3/4] rounded-xl border-2 border-dashed flex flex-col items-center justify-center gap-2 bg-card transition-colors hover:border-foreground/40 disabled:opacity-50 ${
                      photosRejected ? "border-destructive" : "border-input"
                    }`}
                  >
                    <ImagePlus className={`w-7 h-7 text-muted-foreground ${uploading ? "animate-pulse" : ""}`} />
                    <span className="text-[13px] text-muted-foreground font-semibold">
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
                <div className="flex items-center gap-1.5" aria-hidden="true">
                  {Array.from({ length: MAX_PHOTOS }).map((_, i) => (
                    <span
                      key={i}
                      className={`h-1.5 w-6 rounded-full transition-colors ${
                        i < photos.length
                          ? "bg-foreground"
                          : i < MIN_PHOTOS
                            ? "bg-muted-foreground/30"
                            : "bg-muted"
                      }`}
                    />
                  ))}
                </div>
                <p className="text-[13px] font-semibold text-foreground" aria-live="polite">
                  {t("create.photoCount", { count: photos.length, max: MAX_PHOTOS })}
                </p>
                <p className="text-[13px] text-muted-foreground leading-relaxed">
                  {photos.length < MIN_PHOTOS
                    ? t("create.photoMinHint", { min: MIN_PHOTOS })
                    : t("create.photoEnough", { max: MAX_PHOTOS })}
                </p>
              </div>

              {/* Sunucu fotoğrafları reddettiyse (ör. 3'ten az) burada söylenir. */}
              {photosRejected && (
                <p role="alert" className="text-[13px] text-destructive leading-relaxed">
                  {submitError.message}
                </p>
              )}

              {/* Yükleme hatası kullanıcıyı kilitlemez: metin kalır, yeniden
                  denemek için düğme hemen altındadır. */}
              {uploadError && (
                <div
                  role="alert"
                  className="rounded-xl border border-destructive/40 bg-destructive/5 px-4 py-3 space-y-2"
                >
                  <p className="text-[13px] font-semibold text-foreground">{t("common.photoUploadFailed")}</p>
                  <p className="text-[13px] text-muted-foreground leading-relaxed">{uploadError}</p>
                  {photos.length < MAX_PHOTOS && (
                    <button
                      onClick={() => pickPhoto(MAX_PHOTOS - photos.length)}
                      disabled={uploading}
                      className="text-[13px] font-semibold text-secondary hover:underline disabled:opacity-50"
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

      {/* Alttaki düğme: sabit, güvenli alan payıyla */}
      <div className="fixed bottom-0 left-0 right-0 bg-background/95 backdrop-blur-md border-t border-border px-5 pt-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
        <div className="w-full max-w-md mx-auto">
          {/* Gönderim hatası formu kapatmaz; sunucunun açıklaması burada kalır. */}
          {submitError && (
            <div className="mb-3 rounded-xl border border-destructive/40 bg-destructive/5 px-4 py-3 space-y-2">
              <p className="text-[13px] font-semibold text-foreground">
                {submitError.moderation ? t("create.moderationTitle") : t("create.failedTitle")}
              </p>
              {/* Metin ilgili adımda alanın altında duruyorsa burada tekrarlanmaz. */}
              {!shownInline && (
                <p className="text-[13px] text-muted-foreground leading-relaxed">{submitError.message}</p>
              )}
              {!shownInline && errorStep !== undefined && (
                <button
                  onClick={() => setCurrentStep(errorStep)}
                  className="text-[13px] font-semibold text-secondary hover:underline"
                >
                  {errorStep === 3 ? t("create.goToPhotos") : t("create.editTexts")}
                </button>
              )}
            </div>
          )}
          <Button
            size="lg"
            onClick={next}
            disabled={!canProceed() || submitting}
            className="w-full flex h-12 text-base disabled:opacity-40"
          >
            {submitting ? t("create.publishing") : currentStep === totalSteps - 1 ? t("create.publish") : t("common.continue")}
          </Button>
        </div>
      </div>
    </div>
  );
};

/** Adım başlığı: sola yaslı, serif; Onboarding'deki başlıkla aynı ölçü. */
const StepHeader = ({ title, sub }: { title: string; sub: string }) => (
  <div className="space-y-2 pt-8 pb-2">
    <h2 className="text-[2.1rem] text-foreground leading-[1.08]">{title}</h2>
    <p className="text-muted-foreground leading-relaxed">{sub}</p>
  </div>
);

export default CreateListing;
