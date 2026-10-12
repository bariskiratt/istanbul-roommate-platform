import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { BRAND } from "@/lib/brand";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowLeft, Camera, Check, Cigarette, Dog, Wine, Moon, Sun, Clock, X } from "lucide-react";
import { toast } from "sonner";
import { ApiError, fetchLocations, registerUser, requestOtp, verifyOtp, updateMe } from "@/lib/api";
import { filterByQuery } from "@/lib/search";
import { usePhotoUpload } from "@/hooks/use-photo-upload";
import {
  clearOnboardingDraft,
  loadOnboardingDraft,
  profileIncomplete,
  saveOnboardingDraft,
} from "@/lib/onboardingDraft";
import PasswordInput from "@/components/PasswordInput";
import DepartmentPicker from "@/components/DepartmentPicker";
import ThemeToggle from "@/components/ThemeToggle";
import LanguageToggle from "@/components/LanguageToggle";
import { useI18n } from "@/i18n";
import Wordmark from "@/components/campus/Wordmark";
import StudentCard from "@/components/campus/StudentCard";

const STEP_COUNT = 7;
/** Kod doğrulanınca oturum açılır; buradan geriye (e-posta, kod) dönülmez. */
const FIRST_PROFILE_STEP = 2;

const Onboarding = () => {
  const navigate = useNavigate();
  const { isLoggedIn, user, login, setUser } = useAuth();
  const { t, n } = useI18n();
  // Yenilemeden önce girilenler (bkz. lib/onboardingDraft.ts).
  const [draft] = useState(loadOnboardingDraft);
  const [currentStep, setCurrentStep] = useState(() => {
    // Oturum açıksa kod zaten doğrulanmıştır: kaldığı profil adımından sürer.
    if (isLoggedIn) return Math.max(draft.step, FIRST_PROFILE_STEP);
    // Hesap açılmış ama kod girilmemişse kod adımına dönülür; e-postaya
    // gelen kod hâlâ geçerli, gerekirse "tekrar gönder" de orada.
    if (draft.registeredEmail && draft.email === draft.registeredEmail) return 1;
    return 0;
  });
  const [busy, setBusy] = useState(false);
  const [registeredEmail, setRegisteredEmail] = useState(draft.registeredEmail);
  const [email, setEmail] = useState(draft.email);
  const [otp, setOtp] = useState(["", "", "", "", "", ""]);
  const [name, setName] = useState(draft.name);
  const [gender, setGender] = useState(draft.gender);
  const [birthYear, setBirthYear] = useState(draft.birthYear);
  const [department, setDepartment] = useState(draft.department);
  const [year, setYear] = useState(draft.year);
  const [budget, setBudget] = useState(draft.budget);
  const [district, setDistrict] = useState<string[]>(draft.district);
  const [districtSearch, setDistrictSearch] = useState("");
  const [lifestyle, setLifestyle] = useState(draft.lifestyle);
  const [photos, setPhotos] = useState<string[]>(draft.photos);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const passwordChecks = {
    length: password.length >= 8,
    uppercase: /[A-Z]/.test(password),
    number: /[0-9]/.test(password),
  };
  const passwordValid = passwordChecks.length && passwordChecks.uppercase && passwordChecks.number;
  const passwordsMatch = password === confirmPassword && confirmPassword.length > 0;

  const progress = ((currentStep + 1) / STEP_COUNT) * 100;
  // Üniversite e-posta alan adından atanır; oturumdaki kullanıcıdan okunur ki
  // yenilemeden sonra da kartta görünsün.
  const university = user?.university ?? "";
  const firstStep = isLoggedIn ? FIRST_PROFILE_STEP : 0;

  useEffect(() => {
    saveOnboardingDraft({
      step: currentStep, email, registeredEmail, name, gender, birthYear,
      department, year, budget, district, lifestyle, photos,
    });
  }, [currentStep, email, registeredEmail, name, gender, birthYear, department, year, budget, district, lifestyle, photos]);

  useEffect(() => {
    // Kaydı çoktan bitmiş hesabın burada işi yok; formu doldurup profilini
    // ezmesin.
    if (user && !profileIncomplete(user)) navigate("/swipe", { replace: true });
  }, [user, navigate]);

  useEffect(() => {
    // Oturum düştüyse (süresi dolmuş token) profil kaydedilemez: yeni kodla
    // tekrar doğrulansın, girilenler taslakta kalır.
    if (!isLoggedIn && currentStep >= FIRST_PROFILE_STEP) {
      setCurrentStep(registeredEmail && email === registeredEmail ? 1 : 0);
    }
  }, [isLoggedIn, currentStep, email, registeredEmail]);

  // Tercih edilen semtler: liste sabit değil, /api/locations'tan gelir.
  // Aynı queryKey konum seçicide de kullanılıyor; istek bir kez atılır.
  const {
    data: locations = [],
    isLoading: locationsLoading,
    isError: locationsError,
    refetch: refetchLocations,
  } = useQuery({
    queryKey: ["locations"],
    queryFn: fetchLocations,
    staleTime: 24 * 60 * 60 * 1000,
    retry: 2,
  });

  // Türkçe karaktersiz arama ("besiktas" -> Beşiktaş), bkz. lib/search.ts.
  const visibleDistricts = useMemo(
    () => filterByQuery(locations.map(l => l.district), districtSearch, d => d),
    [locations, districtSearch],
  );

  const handleOtpChange = (index: number, value: string) => {
    // Yapıştırma: "123456" gibi çok haneli girdiyi kutulara dağıt
    const digits = value.replace(/\D/g, "");
    if (digits.length > 1) {
      const newOtp = [...otp];
      for (let i = 0; i < 6 - index && i < digits.length; i++) {
        newOtp[index + i] = digits[i];
      }
      setOtp(newOtp);
      document.getElementById(`otp-${Math.min(index + digits.length, 5)}`)?.focus();
      return;
    }
    const newOtp = [...otp];
    newOtp[index] = digits;
    setOtp(newOtp);
    if (digits && index < 5) {
      document.getElementById(`otp-${index + 1}`)?.focus();
    }
  };

  const handleOtpKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === "Backspace" && !otp[index] && index > 0) {
      document.getElementById(`otp-${index - 1}`)?.focus();
    }
  };

  const resendCode = async () => {
    try {
      const res = await requestOtp(email);
      setOtp(["", "", "", "", "", ""]);
      if (res.dev_code) {
        toast.info(t("ob.verifyCode", { code: res.dev_code }), { duration: 30000 });
      } else {
        toast.success(t("ob.codeResent"), {
          description: t("login.codeSentDesc"),
          duration: 8000,
        });
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("ob.codeFailed"));
    }
  };

  const { pick: pickPhoto, uploading } = usePhotoUpload(url =>
    setPhotos(prev => (prev.length < 6 ? [...prev, url] : prev)),
  );

  const canProceed = () => {
    switch (currentStep) {
      case 0: return email.includes("@") && email.includes(".edu.tr") && passwordValid && passwordsMatch;
      case 1: return otp.every(d => d !== "");
      case 2: return name && gender && birthYear;
      case 3: return department && year;  // üniversite otomatik; zorunlu değil
      case 4: return district.length > 0;
      case 5: return true;
      case 6: return photos.length >= 1;
      default: return false;
    }
  };

  const next = async () => {
    try {
      setBusy(true);

      // Adım 0 → 1: hesabı oluştur, doğrulama kodunu iste.
      // Geri dönüp aynı adresle tekrar ilerlenirse ikinci kez register
      // çağrılmaz ("zaten kayıtlı" hatasıyla formu kaybettirmesin); adres
      // düzeltildiyse yeni adres için hesap açılır.
      if (currentStep === 0 && email !== registeredEmail) {
        const res = await registerUser(email, password);
        setRegisteredEmail(email);
        if (res.dev_code) {
          toast.info(t("ob.verifyCode", { code: res.dev_code }), { duration: 30000 });
        } else {
          toast.success(t("ob.codeSentTitle"), {
            description: t("login.codeSentDesc"),
            duration: 8000,
          });
        }
      }

      // Adım 1 → 2: kodu doğrula, oturumu başlat. Şifre de gider: yönetici
      // adresiyle açılan hesapta kod tek başına yetmez (normal hesapta yok
      // sayılır). Sayfa yenilendiyse şifre bellekte yoktur; o durumda
      // yönetici Giriş ekranının "Kodla gir" sekmesinden devam eder.
      if (currentStep === 1) {
        const { token, user } = await verifyOtp(email, otp.join(""), password || undefined);
        login(token, user);
      }

      // Son adım: profili kaydet
      if (currentStep === STEP_COUNT - 1) {
        const me = await updateMe({
          name,
          gender,
          birth_year: Number(birthYear),
          department,
          year: Number(year),
          budget_min: budget[0],
          budget_max: budget[1],
          smoking: lifestyle.smoking,
          alcohol: lifestyle.alcohol,
          pets: lifestyle.pets,
          sleep_schedule: lifestyle.sleep,
          preferred_districts: district,
          photos,
        });
        setUser(me);
        clearOnboardingDraft();
        toast.success(t("ob.profileReady"));
        navigate("/swipe");
        return;
      }

      setCurrentStep(s => s + 1);
    } catch (err) {
      const message = err instanceof Error ? err.message : t("common.error");
      toast.error(message);
      // Kayıtlı e-posta ile tekrar denenmişse girişe yönlendir. Hata metnine
      // değil HTTP koduna bakılır: metin backend'in dilinden bağımsız değil.
      if (err instanceof ApiError && err.status === 409) navigate("/login");
    } finally {
      setBusy(false);
    }
  };

  const back = () => {
    if (currentStep > firstStep) setCurrentStep(s => s - 1);
  };

  const stepTitles = [
    t("ob.step1Title"), t("ob.step2Title"), t("ob.step3Title"), t("ob.step4Title"),
    t("ob.step5Title"), t("ob.step6Title"), t("ob.step7Title"),
  ];
  const stepSubtitles = [
    t("ob.step1Sub"),
    t("ob.step2Sub", { email: email || t("ob.emailFallback") }),
    t("ob.step3Sub"), t("ob.step4Sub"), t("ob.step5Sub"), t("ob.step6Sub"), t("ob.step7Sub"),
  ];

  // Kayıt bir öğrenci kartı doldurmak gibi ilerler: kod doğrulandıktan sonra
  // ad, bölüm ve fotoğraf adımlarında kart canlı olarak dolar.
  const showCard = currentStep === 2 || currentStep === 3 || currentStep === 6;

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Üst çubuk: geri, adım sayacı, dil ve tema */}
      <div className="px-4 h-16 flex items-center gap-2 border-b border-border">
        {currentStep > firstStep ? (
          <button
            onClick={back}
            aria-label={t("common.back")}
            className="w-10 h-10 rounded-full flex items-center justify-center text-foreground hover:bg-muted transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
        ) : (
          <Link to="/" className="pl-1" aria-label={BRAND}><Wordmark size="sm" /></Link>
        )}
        <span className="flex-1 text-[13px] text-muted-foreground text-center tabular-nums">
          {t("ob.stepCounter", { current: currentStep + 1, total: STEP_COUNT })}
        </span>
        <LanguageToggle />
        <ThemeToggle />
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
          className="flex-1 w-full max-w-md mx-auto px-5 pb-36 overflow-y-auto"
        >
          {/* Step header */}
          <div className="space-y-2 pt-8 pb-7">
            <h2 className="text-[2.1rem] text-foreground leading-[1.08]">{stepTitles[currentStep]}</h2>
            <p className="text-muted-foreground leading-relaxed">{stepSubtitles[currentStep]}</p>
          </div>

          {showCard && (
            <StudentCard
              name={name}
              photo={photos[0]}
              university={university || null}
              department={department || null}
              year={year ? Number(year) : null}
              verified={!!university}
              className="mb-7"
            />
          )}

          {/* Step 0: Email */}
          {currentStep === 0 && (
            <div className="space-y-5">
              <div className="space-y-2">
                <Input
                  type="email"
                  placeholder={t("login.emailPlaceholder")}
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  autoComplete="email"
                  className="h-12 text-base"
                />
                {email.length > 3 && !email.includes(".edu.tr") && (
                  <p className="text-xs text-destructive pt-1">
                    {t("ob.eduOnly")}
                  </p>
                )}
              </div>

              {/* Password */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">{t("ob.createPassword")}</label>
                <PasswordInput
                  placeholder={t("ob.passwordPlaceholder")}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  className="h-12 text-base"
                />
                {password.length > 0 && (
                  <div className="space-y-1 pt-1">
                    {[
                      { ok: passwordChecks.length, text: t("ob.ruleLength") },
                      { ok: passwordChecks.uppercase, text: t("ob.ruleUpper") },
                      { ok: passwordChecks.number, text: t("ob.ruleNumber") },
                    ].map(rule => (
                      <div key={rule.text} className="flex items-center gap-2 text-xs">
                        <Check className={`w-3.5 h-3.5 ${rule.ok ? "text-accent" : "text-muted-foreground/40"}`} />
                        <span className={rule.ok ? "text-accent" : "text-muted-foreground"}>{rule.text}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Confirm Password */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">{t("ob.repeatPassword")}</label>
                <PasswordInput
                  placeholder={t("ob.repeatPlaceholder")}
                  value={confirmPassword}
                  onChange={e => setConfirmPassword(e.target.value)}
                  className="h-12 text-base"
                />
                {confirmPassword.length > 0 && !passwordsMatch && (
                  <p className="text-xs text-destructive pt-1">{t("ob.passwordMismatch")}</p>
                )}
              </div>
            </div>
          )}

          {/* Step 1: OTP */}
          {currentStep === 1 && (
            <div className="space-y-6">
              <div className="flex gap-2 sm:gap-3">
                {otp.map((digit, i) => (
                  <Input
                    key={i}
                    id={`otp-${i}`}
                    type="text"
                    inputMode="numeric"
                    value={digit}
                    onChange={e => handleOtpChange(i, e.target.value)}
                    onKeyDown={e => handleOtpKeyDown(i, e)}
                    aria-label={t("ob.otpDigit", { n: i + 1 })}
                    className="w-11 sm:w-14 h-14 px-0 text-center text-2xl font-display font-semibold"
                  />
                ))}
              </div>
              <p className="text-sm text-muted-foreground">
                {t("ob.noCode")}{" "}
                <button type="button" onClick={resendCode} className="text-secondary font-semibold underline-offset-4 hover:underline">
                  {t("ob.resend")}
                </button>
              </p>
            </div>
          )}

          {/* Step 2: Personal */}
          {currentStep === 2 && (
            <div className="space-y-5">
              <Input
                placeholder={t("ob.namePlaceholder")}
                value={name}
                onChange={e => setName(e.target.value)}
                className="h-12 text-base"
              />
              <div className="space-y-3">
                <p className="text-sm font-medium text-foreground">{t("ob.gender")}</p>
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { value: "erkek", label: t("ob.male") },
                    { value: "kadın", label: t("ob.female") },
                    { value: "belirtmek_istemiyorum", label: t("ob.preferNot") },
                  ].map(g => (
                    <button
                      key={g.value}
                      onClick={() => setGender(g.value)}
                      aria-pressed={gender === g.value}
                      className={`flex items-center justify-center min-h-[3.25rem] px-2 py-2 rounded-xl border transition-colors ${
                        gender === g.value
                          ? "border-foreground bg-foreground text-background"
                          : "border-input bg-card text-foreground hover:border-foreground/40"
                      }`}
                    >
                      <span className="text-[13px] font-semibold text-center whitespace-pre-line leading-tight">{g.label}</span>
                    </button>
                  ))}
                </div>
              </div>
              {/* Yaş 17-30 ile sınırlı (üniversite öğrencisi platformu) */}
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">{t("ob.birthYear")}</label>
                <select
                  value={birthYear}
                  onChange={e => setBirthYear(e.target.value)}
                  className="w-full h-12 rounded-xl bg-card border border-input px-3.5 text-base text-foreground outline-none hover:border-foreground/30 focus:border-secondary focus:ring-[3px] focus:ring-secondary/20"
                >
                  <option value="">{t("ob.select")}</option>
                  {Array.from({ length: 14 }, (_, i) => new Date().getFullYear() - 17 - i).map(y => (
                    <option key={y} value={y}>
                      {y} ({t("ob.ageSuffix", { age: new Date().getFullYear() - y })})
                    </option>
                  ))}
                </select>
              </div>
            </div>
          )}

          {/* Step 3: University */}
          {currentStep === 3 && (
            <div className="space-y-5">
              {/* Üniversite e-posta alan adından otomatik atanır; elle girilemez */}
              {!university && (
                <div className="rounded-xl border border-border bg-muted/50 p-4">
                  <p className="text-sm font-semibold text-foreground">{t("ob.universityUnknown")}</p>
                  <p className="text-[13px] text-muted-foreground mt-1">{t("ob.universityNote")}</p>
                </div>
              )}
              <DepartmentPicker value={department} onChange={setDepartment} />
              <div className="space-y-3">
                <p className="text-sm font-medium text-foreground">{t("ob.whichYear")}</p>
                <div className="grid grid-cols-4 gap-3">
                  {["1", "2", "3", "4"].map(y => (
                    <button
                      key={y}
                      onClick={() => setYear(y)}
                      aria-pressed={year === y}
                      className={`h-12 rounded-xl border text-sm font-semibold transition-colors ${
                        year === y
                          ? "border-foreground bg-foreground text-background"
                          : "border-input bg-card text-foreground hover:border-foreground/40"
                      }`}
                    >
                      {t("ob.yearOption", { year: y })}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Step 4: Budget + District */}
          {currentStep === 4 && (
            <div className="space-y-6">
              <div className="rounded-2xl border border-border p-5 space-y-5">
                <div>
                  <p className="text-sm text-muted-foreground mb-1.5">{t("ob.budgetLabel")}</p>
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
              <div className="space-y-3">
                <p className="text-sm font-medium text-foreground">{t("ob.districts")}</p>
                <Input
                  placeholder={t("ob.districtSearch")}
                  value={districtSearch}
                  onChange={e => setDistrictSearch(e.target.value)}
                  // Esc aramayı temizler; seçilen semtler korunur.
                  onKeyDown={e => { if (e.key === "Escape") setDistrictSearch(""); }}
                  className="h-11 text-[15px]"
                />
                <div className="max-h-[240px] overflow-y-auto pr-1">
                  {locationsLoading && (
                    <p className="py-4 text-sm text-muted-foreground">{t("loc.loading")}</p>
                  )}
                  {!locationsLoading && (locationsError || locations.length === 0) && (
                    <div className="py-4 space-y-2">
                      <p className="text-sm text-muted-foreground">{t("loc.loadFailed")}</p>
                      <button
                        type="button"
                        onClick={() => refetchLocations()}
                        className="text-sm font-semibold text-secondary hover:underline"
                      >
                        {t("common.retry")}
                      </button>
                    </div>
                  )}
                  {locations.length > 0 && visibleDistricts.length === 0 && (
                    <p className="py-4 text-sm text-muted-foreground">{t("loc.noDistrictMatch")}</p>
                  )}
                  <div className="flex flex-wrap gap-2">
                    {visibleDistricts.map(d => (
                      <button
                        key={d}
                        onClick={() => setDistrict(prev =>
                          prev.includes(d) ? prev.filter(x => x !== d) : [...prev, d]
                        )}
                        aria-pressed={district.includes(d)}
                        className={`px-3.5 py-2 rounded-full text-sm font-medium border transition-colors ${
                          district.includes(d)
                            ? "bg-foreground text-background border-foreground"
                            : "bg-card border-input text-foreground hover:border-foreground/40"
                        }`}
                      >
                        {d}
                      </button>
                    ))}
                  </div>
                </div>
                {district.length > 0 && (
                  <p className="text-xs text-muted-foreground">{t("ob.districtsSelected", { count: district.length })}</p>
                )}
              </div>
            </div>
          )}

          {/* Step 5: Lifestyle */}
          {currentStep === 5 && (
            <div className="space-y-4">
              {[
                { key: "smoking" as const, icon: Cigarette, label: t("ob.smoking"), desc: t("ob.smokingDesc") },
                { key: "alcohol" as const, icon: Wine, label: t("ob.alcohol"), desc: t("ob.alcoholDesc") },
                { key: "pets" as const, icon: Dog, label: t("ob.pets"), desc: t("ob.petsDesc") },
              ].map(item => (
                <button
                  key={item.key}
                  onClick={() => setLifestyle(l => ({ ...l, [item.key]: !l[item.key] }))}
                  role="switch"
                  aria-checked={lifestyle[item.key]}
                  className={`w-full flex items-center gap-4 p-4 rounded-2xl border transition-colors ${
                    lifestyle[item.key]
                      ? "border-foreground bg-card"
                      : "border-border bg-card hover:border-foreground/40"
                  }`}
                >
                  <item.icon className={`w-6 h-6 shrink-0 ${lifestyle[item.key] ? "text-foreground" : "text-muted-foreground"}`} strokeWidth={1.8} />
                  <div className="flex-1 text-left">
                    <p className="font-semibold text-foreground">{item.label}</p>
                    <p className="text-xs text-muted-foreground">{item.desc}</p>
                  </div>
                  <div className={`w-12 h-7 shrink-0 rounded-full p-0.5 transition-colors ${
                    lifestyle[item.key] ? "bg-primary" : "bg-input"
                  }`}>
                    <motion.div
                      className="w-6 h-6 rounded-full bg-card shadow-sm"
                      animate={{ x: lifestyle[item.key] ? 20 : 0 }}
                      transition={{ type: "spring", stiffness: 500, damping: 30 }}
                    />
                  </div>
                </button>
              ))}

              <div className="pt-4 space-y-3">
                <p className="text-sm font-medium text-foreground">{t("ob.sleepTitle")}</p>
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { value: "erken", label: t("ob.sleepEarly"), icon: Sun },
                    { value: "gece", label: t("ob.sleepNight"), icon: Moon },
                    { value: "esnek", label: t("ob.sleepFlexible"), icon: Clock },
                  ].map(s => (
                    <button
                      key={s.value}
                      onClick={() => setLifestyle(l => ({ ...l, sleep: s.value }))}
                      aria-pressed={lifestyle.sleep === s.value}
                      className={`flex flex-col items-center gap-2 py-4 px-2 rounded-xl border transition-colors ${
                        lifestyle.sleep === s.value
                          ? "border-foreground bg-foreground text-background"
                          : "border-input bg-card text-foreground hover:border-foreground/40"
                      }`}
                    >
                      <s.icon className="w-5 h-5" strokeWidth={1.8} />
                      <span className="text-[13px] font-semibold">{s.label}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Step 6: Photos */}
          {currentStep === 6 && (
            <div className="grid grid-cols-3 gap-3">
              {photos.map((photo, i) => (
                <div key={i} className="aspect-[3/4] rounded-xl overflow-hidden border border-border relative">
                  <img src={photo} alt="" className="w-full h-full object-cover" />
                  {/* Dokunmatik ekranda üzerine gelme yok: kaldır düğmesi hep görünür */}
                  <button
                    onClick={() => setPhotos(prev => prev.filter((_, j) => j !== i))}
                    aria-label={t("pedit.removePhoto")}
                    title={t("pedit.removePhoto")}
                    className="absolute top-1.5 right-1.5 w-7 h-7 rounded-full bg-background/90 text-foreground flex items-center justify-center hover:bg-background transition-colors"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
              {photos.length < 6 && (
                <button
                  onClick={() => pickPhoto(6 - photos.length)}
                  disabled={uploading}
                  className="aspect-[3/4] rounded-xl border-2 border-dashed border-input flex flex-col items-center justify-center gap-2 bg-card hover:border-foreground/40 transition-colors disabled:opacity-50"
                >
                  <Camera className={`w-8 h-8 text-muted-foreground ${uploading ? "animate-pulse" : ""}`} />
                  <span className="text-xs text-muted-foreground font-medium">
                    {t(uploading ? "ob.uploading" : "ob.addPhoto")}
                  </span>
                </button>
              )}
            </div>
          )}
        </motion.div>
      </AnimatePresence>

      {/* Alttaki düğme: sabit, güvenli alan payıyla */}
      <div className="fixed bottom-0 left-0 right-0 bg-background/95 backdrop-blur-md border-t border-border px-5 pt-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
        <Button
          size="lg"
          onClick={next}
          disabled={!canProceed() || busy}
          className="w-full max-w-md mx-auto flex h-12 text-base disabled:opacity-40"
        >
          {busy ? t("login.busy") : t(currentStep === STEP_COUNT - 1 ? "ob.start" : "common.continue")}
        </Button>
      </div>
    </div>
  );
};

export default Onboarding;
