import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowLeft, ArrowRight, Mail, KeyRound, Camera, Check, Cigarette, Dog, Wine, Moon, Sun, Clock, User, GraduationCap, MapPin, Heart, Eye, EyeOff } from "lucide-react";
import { toast } from "sonner";
import { registerUser, verifyOtp, updateMe } from "@/lib/api";
import { usePhotoUpload } from "@/hooks/use-photo-upload";

const steps = ["E-posta", "OTP", "Kişisel", "Üniversite", "Bütçe", "Yaşam Tarzı", "Fotoğraf"];

const Onboarding = () => {
  const navigate = useNavigate();
  const { login, setUser } = useAuth();
  const [currentStep, setCurrentStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState(["", "", "", "", "", ""]);
  const [name, setName] = useState("");
  const [gender, setGender] = useState("");
  const [birthYear, setBirthYear] = useState("");
  const [university, setUniversity] = useState("");
  const [department, setDepartment] = useState("");
  const [year, setYear] = useState("");
  const [budget, setBudget] = useState([4000, 8000]);
  const [district, setDistrict] = useState<string[]>([]);
  const [districtSearch, setDistrictSearch] = useState("");
  const [lifestyle, setLifestyle] = useState({ smoking: false, alcohol: false, pets: false, sleep: "esnek" });
  const [photos, setPhotos] = useState<string[]>([]);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const passwordChecks = {
    length: password.length >= 8,
    uppercase: /[A-Z]/.test(password),
    number: /[0-9]/.test(password),
  };
  const passwordValid = passwordChecks.length && passwordChecks.uppercase && passwordChecks.number;
  const passwordsMatch = password === confirmPassword && confirmPassword.length > 0;

  const progress = ((currentStep + 1) / steps.length) * 100;

  const handleOtpChange = (index: number, value: string) => {
    if (value.length > 1) return;
    const newOtp = [...otp];
    newOtp[index] = value;
    setOtp(newOtp);
    if (value && index < 5) {
      const next = document.getElementById(`otp-${index + 1}`);
      next?.focus();
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
      case 3: return university && department && year;
      case 4: return district.length > 0;
      case 5: return true;
      case 6: return photos.length >= 1;
      default: return false;
    }
  };

  const next = async () => {
    try {
      setBusy(true);

      // Adım 0 → 1: hesabı oluştur, doğrulama kodunu iste
      if (currentStep === 0) {
        const res = await registerUser(email, password);
        // E-posta servisi bağlanana kadar kod dev modda yanıtla gelir.
        if (res.dev_code) {
          toast.info(`Doğrulama kodun: ${res.dev_code}`, { duration: 30000 });
        }
      }

      // Adım 1 → 2: kodu doğrula, oturumu başlat
      if (currentStep === 1) {
        const { token, user } = await verifyOtp(email, otp.join(""));
        login(token, user);
      }

      // Son adım: profili kaydet
      if (currentStep === steps.length - 1) {
        const me = await updateMe({
          name,
          gender,
          birth_year: Number(birthYear),
          university,
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
        toast.success("Profilin hazır! 🎉");
        navigate("/swipe");
        return;
      }

      setCurrentStep(s => s + 1);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Bir şeyler ters gitti";
      toast.error(message);
      // Kayıtlı e-posta ile tekrar denenmişse girişe yönlendir
      if (message.includes("zaten kayıtlı")) navigate("/login");
    } finally {
      setBusy(false);
    }
  };

  const back = () => {
    if (currentStep > 0) setCurrentStep(s => s - 1);
  };

  const stepIcons = [Mail, KeyRound, User, GraduationCap, MapPin, Heart, Camera];
  const stepTitles = [
    "Üniversite E-postan",
    "Doğrulama Kodu",
    "Seni Tanıyalım",
    "Eğitim Bilgilerin",
    "Bütçe ve Konum",
    "Yaşam Tarzın",
    "Fotoğrafların",
  ];
  const stepSubtitles = [
    "Sadece .edu.tr uzantılı e-postalar kabul edilir",
    `${email || "E-posta"} adresine gönderilen 6 haneli kodu gir`,
    "Temel bilgilerini paylaş",
    "Üniversite ve bölüm bilgilerin",
    "Bütçeni ve tercih ettiğin semti seç",
    "Ev arkadaşı uyumun için önemli bilgiler",
    "En az 1 fotoğraf yüklemen gerekiyor",
  ];

  const StepIcon = stepIcons[currentStep];

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Top bar */}
      <div className="px-6 pt-4 pb-2 flex items-center gap-3">
        {currentStep > 0 && (
          <button
            onClick={back}
            className="w-10 h-10 rounded-full bg-card flex items-center justify-center text-foreground hover:bg-muted transition-colors"
            style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
        )}
        <div className="flex-1" />
      </div>

      {/* Progress — thin animated bar */}
      <div className="px-6 pb-2">
        <div className="h-[3px] w-full bg-muted rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-gradient-to-r from-primary to-secondary rounded-full"
            initial={{ width: 0 }}
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
          {/* Step header */}
          <div className="text-center space-y-3 pt-6 pb-8">
            <div className="w-16 h-16 rounded-2xl bg-lavender/50 flex items-center justify-center mx-auto">
              <StepIcon className="w-8 h-8 text-primary" />
            </div>
            <h2 className="text-[28px] font-bold text-foreground leading-tight">{stepTitles[currentStep]}</h2>
            <p className="text-muted-foreground text-sm max-w-[280px] mx-auto">{stepSubtitles[currentStep]}</p>
          </div>

          {/* Step 0: Email */}
          {currentStep === 0 && (
            <div className="space-y-5">
              <Input
                type="email"
                placeholder="öğrenci@üniversite.edu.tr"
                value={email}
                onChange={e => setEmail(e.target.value)}
                className="h-14 text-base rounded-2xl bg-card border-border shadow-sm focus:shadow-md focus:ring-2 focus:ring-primary/20 transition-shadow"
              />

              {/* Password */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">Şifre oluştur</label>
                <div className="relative">
                  <Input
                    type={showPassword ? "text" : "password"}
                    placeholder="En az 8 karakter"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    className="h-14 text-base rounded-2xl bg-card border-border shadow-sm focus:shadow-md focus:ring-2 focus:ring-primary/20 transition-shadow pr-12"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(v => !v)}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
                {password.length > 0 && (
                  <div className="space-y-1 pt-1">
                    {[
                      { ok: passwordChecks.length, text: "En az 8 karakter" },
                      { ok: passwordChecks.uppercase, text: "En az 1 büyük harf" },
                      { ok: passwordChecks.number, text: "En az 1 rakam" },
                    ].map(rule => (
                      <div key={rule.text} className="flex items-center gap-2 text-xs">
                        <Check className={`w-3.5 h-3.5 ${rule.ok ? "text-green-500" : "text-muted-foreground/40"}`} />
                        <span className={rule.ok ? "text-green-600" : "text-muted-foreground"}>{rule.text}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Confirm Password */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">Şifreyi tekrarla</label>
                <div className="relative">
                  <Input
                    type={showConfirmPassword ? "text" : "password"}
                    placeholder="Şifreni tekrar gir"
                    value={confirmPassword}
                    onChange={e => setConfirmPassword(e.target.value)}
                    className="h-14 text-base rounded-2xl bg-card border-border shadow-sm focus:shadow-md focus:ring-2 focus:ring-primary/20 transition-shadow pr-12"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(v => !v)}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {showConfirmPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
                {confirmPassword.length > 0 && !passwordsMatch && (
                  <p className="text-xs text-destructive pt-1">Şifreler eşleşmiyor</p>
                )}
              </div>
            </div>
          )}

          {/* Step 1: OTP */}
          {currentStep === 1 && (
            <div className="space-y-6">
              <div className="flex gap-3 justify-center">
                {otp.map((digit, i) => (
                  <Input
                    key={i}
                    id={`otp-${i}`}
                    type="text"
                    inputMode="numeric"
                    maxLength={1}
                    value={digit}
                    onChange={e => handleOtpChange(i, e.target.value)}
                    className="w-14 h-14 text-center text-2xl font-bold rounded-2xl bg-card border-border shadow-sm focus:shadow-md focus:ring-2 focus:ring-primary/20 transition-shadow"
                  />
                ))}
              </div>
              <p className="text-center text-sm text-muted-foreground">
                Kod gelmedi mi? <button className="text-primary font-semibold">Tekrar gönder</button>
              </p>
            </div>
          )}

          {/* Step 2: Personal */}
          {currentStep === 2 && (
            <div className="space-y-5">
              <Input
                placeholder="Adın ne? (ör. Zeynep, Mehmet)"
                value={name}
                onChange={e => setName(e.target.value)}
                className="h-14 text-base rounded-2xl bg-card border-border shadow-sm focus:shadow-md focus:ring-2 focus:ring-primary/20 transition-shadow"
              />
              <div className="space-y-3">
                <p className="text-sm font-medium text-foreground">Cinsiyet</p>
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { value: "erkek", label: "Erkek", icon: "👨" },
                    { value: "kadın", label: "Kadın", icon: "👩" },
                    { value: "belirtmek_istemiyorum", label: "Belirtmek\nistemiyorum", icon: "🤝" },
                  ].map(g => (
                    <button
                      key={g.value}
                      onClick={() => setGender(g.value)}
                      className={`flex flex-col items-center gap-2 p-4 rounded-2xl border-2 transition-all ${
                        gender === g.value
                          ? "border-secondary bg-lavender/30 shadow-md"
                          : "border-border bg-card hover:border-primary/30 hover:shadow-sm"
                      }`}
                    >
                      <span className="text-2xl">{g.icon}</span>
                      <span className="text-xs font-medium text-center whitespace-pre-line">{g.label}</span>
                    </button>
                  ))}
                </div>
              </div>
              <Input
                type="number"
                placeholder="Doğum yılın (ör. 2002)"
                value={birthYear}
                onChange={e => setBirthYear(e.target.value)}
                className="h-14 text-base rounded-2xl bg-card border-border shadow-sm focus:shadow-md focus:ring-2 focus:ring-primary/20 transition-shadow"
              />
            </div>
          )}

          {/* Step 3: University */}
          {currentStep === 3 && (
            <div className="space-y-5">
              <Input
                placeholder="Üniversiteni yaz... (ör. İTÜ, Boğaziçi)"
                value={university}
                onChange={e => setUniversity(e.target.value)}
                className="h-14 text-base rounded-2xl bg-card border-border shadow-sm focus:shadow-md focus:ring-2 focus:ring-primary/20 transition-shadow"
              />
              <Input
                placeholder="Bölümün? (ör. Bilgisayar Müh., Psikoloji)"
                value={department}
                onChange={e => setDepartment(e.target.value)}
                className="h-14 text-base rounded-2xl bg-card border-border shadow-sm focus:shadow-md focus:ring-2 focus:ring-primary/20 transition-shadow"
              />
              <div className="space-y-3">
                <p className="text-sm font-medium text-foreground">Kaçıncı Sınıf?</p>
                <div className="grid grid-cols-4 gap-3">
                  {["1", "2", "3", "4"].map(y => (
                    <button
                      key={y}
                      onClick={() => setYear(y)}
                      className={`p-4 rounded-2xl border-2 text-sm font-bold transition-all ${
                        year === y
                          ? "border-secondary bg-lavender/30 shadow-md"
                          : "border-border bg-card hover:border-primary/30 hover:shadow-sm"
                      }`}
                    >
                      {y}. Sınıf
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Step 4: Budget + District */}
          {currentStep === 4 && (
            <div className="space-y-6">
              <div className="card-listing p-6 space-y-5">
                <div className="text-center">
                  <p className="text-sm text-muted-foreground mb-1">Aylık Kira Bütçesi</p>
                  <p className="text-2xl font-bold text-primary">
                    {budget[0].toLocaleString("tr-TR")} ₺ — {budget[1].toLocaleString("tr-TR")} ₺
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
                  <span>1.000 ₺</span>
                  <span>20.000 ₺</span>
                </div>
              </div>
              <div className="space-y-3">
                <p className="text-sm font-medium text-foreground">Tercih Edilen Semtler</p>
                <Input
                  placeholder="İstanbul'da bir semt ara... (ör. Sarıyer, Maltepe)"
                  value={districtSearch}
                  onChange={e => setDistrictSearch(e.target.value)}
                  className="h-12 text-sm rounded-xl bg-card border-border shadow-sm focus:shadow-md focus:ring-2 focus:ring-primary/20 transition-shadow"
                />
                <div className="max-h-[240px] overflow-y-auto pr-1">
                  <div className="flex flex-wrap gap-2">
                    {["Kadıköy", "Beşiktaş", "Üsküdar", "Şişli", "Bakırköy", "Beyoğlu", "Sarıyer", "Fatih", "Eyüpsultan", "Maltepe", "Ataşehir", "Pendik", "Kartal", "Bağcılar", "Bahçelievler", "Zeytinburnu", "Gaziosmanpaşa", "Sultangazi", "Esenler", "Güngören", "Bayrampaşa", "Küçükçekmece", "Büyükçekmece", "Silivri", "Arnavutköy", "Başakşehir"]
                      .filter(d => d.toLowerCase().includes(districtSearch.toLowerCase()))
                      .map(d => (
                        <button
                          key={d}
                          onClick={() => setDistrict(prev =>
                            prev.includes(d) ? prev.filter(x => x !== d) : [...prev, d]
                          )}
                          className={`px-3.5 py-2 rounded-full text-sm font-medium transition-all ${
                            district.includes(d)
                              ? "bg-primary text-primary-foreground shadow-sm"
                              : "bg-card border border-[hsl(var(--muted-foreground)/0.3)] text-foreground hover:border-primary/40"
                          }`}
                        >
                          {d}
                        </button>
                      ))}
                  </div>
                </div>
                {district.length > 0 && (
                  <p className="text-xs text-muted-foreground">{district.length} semt seçildi</p>
                )}
              </div>
            </div>
          )}

          {/* Step 5: Lifestyle */}
          {currentStep === 5 && (
            <div className="space-y-4">
              {[
                { key: "smoking" as const, icon: Cigarette, label: "Sigara", desc: "Sigara kullanıyor musun?" },
                { key: "alcohol" as const, icon: Wine, label: "Alkol", desc: "Alkol kullanıyor musun?" },
                { key: "pets" as const, icon: Dog, label: "Evcil Hayvan", desc: "Evcil hayvan dostu musun?" },
              ].map(item => (
                <button
                  key={item.key}
                  onClick={() => setLifestyle(l => ({ ...l, [item.key]: !l[item.key] }))}
                  className={`w-full flex items-center gap-4 p-5 rounded-2xl border-2 transition-all ${
                    lifestyle[item.key]
                      ? "border-primary bg-primary/5 shadow-md"
                      : "border-border bg-card hover:shadow-sm"
                  }`}
                >
                  <div className={`w-12 h-12 rounded-2xl flex items-center justify-center transition-colors ${
                    lifestyle[item.key] ? "bg-primary text-primary-foreground" : "bg-lavender/50 text-muted-foreground"
                  }`}>
                    <item.icon className="w-6 h-6" />
                  </div>
                  <div className="flex-1 text-left">
                    <p className="font-semibold text-foreground">{item.label}</p>
                    <p className="text-xs text-muted-foreground">{item.desc}</p>
                  </div>
                  <div className={`w-12 h-7 rounded-full p-0.5 transition-colors ${
                    lifestyle[item.key] ? "bg-primary" : "bg-muted"
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
                <p className="text-sm font-medium text-foreground">Uyku Düzeni</p>
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { value: "erken", label: "Erken Kalkar", icon: Sun, emoji: "🌅" },
                    { value: "gece", label: "Gece Kuşu", icon: Moon, emoji: "🌙" },
                    { value: "esnek", label: "Esnek", icon: Clock, emoji: "⏰" },
                  ].map(s => (
                    <button
                      key={s.value}
                      onClick={() => setLifestyle(l => ({ ...l, sleep: s.value }))}
                      className={`flex flex-col items-center gap-3 p-5 rounded-2xl border-2 transition-all ${
                        lifestyle.sleep === s.value
                          ? "border-secondary bg-lavender/30 shadow-md"
                          : "border-border bg-card hover:border-primary/30 hover:shadow-sm"
                      }`}
                    >
                      <span className="text-2xl">{s.emoji}</span>
                      <span className="text-xs font-medium">{s.label}</span>
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
                <div key={i} className="aspect-square rounded-2xl overflow-hidden border-2 border-primary relative shadow-md">
                  <img src={photo} alt="" className="w-full h-full object-cover" />
                  <div className="absolute top-2 right-2 w-6 h-6 rounded-full bg-accent flex items-center justify-center">
                    <Check className="w-4 h-4 text-accent-foreground" />
                  </div>
                </div>
              ))}
              {photos.length < 6 && (
                <button
                  onClick={pickPhoto}
                  disabled={uploading}
                  className="aspect-square rounded-2xl border-2 border-dashed border-muted-foreground/30 flex flex-col items-center justify-center gap-2 bg-card hover:bg-lavender/20 transition-all hover:border-primary/40 hover:shadow-sm disabled:opacity-50"
                >
                  <Camera className={`w-8 h-8 text-muted-foreground ${uploading ? "animate-pulse" : ""}`} />
                  <span className="text-xs text-muted-foreground font-medium">
                    {uploading ? "Yükleniyor…" : "Ekle"}
                  </span>
                </button>
              )}
            </div>
          )}
        </motion.div>
      </AnimatePresence>

      {/* Bottom CTA — fixed, gradient, safe area */}
      <div className="fixed bottom-0 left-0 right-0 bg-card/80 backdrop-blur-lg p-6 pb-[max(1.5rem,env(safe-area-inset-bottom))]" style={{ boxShadow: '0 -1px 0 rgba(0,0,0,0.04)' }}>
        <Button
          onClick={next}
          disabled={!canProceed() || busy}
          className="w-full h-14 text-base font-bold bg-gradient-to-r from-primary to-secondary text-primary-foreground hover:opacity-90 shadow-lg disabled:opacity-40"
        >
          {busy ? "Bekleyin..." : currentStep === steps.length - 1 ? "Başla" : "Devam Et"}
          <ArrowRight className="w-5 h-5 ml-2" />
        </Button>
      </div>
    </div>
  );
};

export default Onboarding;
