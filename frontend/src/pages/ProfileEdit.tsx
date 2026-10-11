import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check, X, ImagePlus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import BottomNav from "@/components/layout/BottomNav";
import AppHeader from "@/components/layout/AppHeader";
import StudentCard from "@/components/campus/StudentCard";
import { useAuth } from "@/contexts/AuthContext";
import { updateMe } from "@/lib/api";
import { usePhotoUpload } from "@/hooks/use-photo-upload";
import DepartmentPicker from "@/components/DepartmentPicker";
import { useI18n } from "@/i18n";

const DISTRICTS = ["Kadıköy", "Beşiktaş", "Üsküdar", "Şişli", "Bakırköy", "Beyoğlu", "Sarıyer", "Fatih", "Eyüpsultan", "Maltepe", "Ataşehir", "Pendik", "Kartal", "Bahçelievler", "Zeytinburnu", "Küçükçekmece", "Başakşehir"];

const ProfileEdit = () => {
  const navigate = useNavigate();
  const { user: me, setUser } = useAuth();
  const { t, n } = useI18n();

  const [name, setName] = useState(me?.name ?? "");
  const [department, setDepartment] = useState(me?.department ?? "");
  const [year, setYear] = useState(me?.year ?? 1);
  const [budget, setBudget] = useState<number[]>([
    me?.budget_min ?? 4000,
    me?.budget_max ?? 8000,
  ]);
  const [districts, setDistricts] = useState<string[]>(me?.preferred_districts ?? []);
  const [smoking, setSmoking] = useState(me?.smoking ?? false);
  const [alcohol, setAlcohol] = useState(me?.alcohol ?? false);
  const [pets, setPets] = useState(me?.pets ?? false);
  const [sleep, setSleep] = useState(me?.sleep_schedule ?? "esnek");
  const [bio, setBio] = useState(me?.bio ?? "");
  const [photos, setPhotos] = useState<string[]>(me?.photos ?? []);
  const [saving, setSaving] = useState(false);

  const { pick: pickPhoto, uploading } = usePhotoUpload(url =>
    setPhotos(prev => (prev.length < 6 ? [...prev, url] : prev)),
  );

  if (!me) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-muted-foreground">{t("pedit.loginRequired")}</p>
      </div>
    );
  }

  const save = async () => {
    setSaving(true);
    try {
      const updated = await updateMe({
        name,
        department,
        year,
        budget_min: budget[0],
        budget_max: budget[1],
        preferred_districts: districts,
        smoking,
        alcohol,
        pets,
        sleep_schedule: sleep,
        bio,
        photos,
      });
      setUser(updated);
      toast.success(t("pedit.saved"));
      navigate("/profile");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("pedit.saveFailed"));
    } finally {
      setSaving(false);
    }
  };

  // Seçili seçenek mürekkeple dolar (Onboarding ile aynı dil).
  const choice = (selected: boolean) =>
    selected
      ? "border-foreground bg-foreground text-background"
      : "border-input bg-card text-foreground hover:border-foreground/40";

  return (
    <div className="min-h-screen bg-background pb-40">
      <AppHeader title={t("pedit.title")} showBack onBack={() => navigate("/profile")} hideControls />

      <div className="px-5 py-6 space-y-10 max-w-lg mx-auto">
        {/* Kart, yazdıkça güncellenir: başkalarının göreceği hâl budur. */}
        <StudentCard
          name={name || t("messages.unnamed")}
          photo={photos[0]}
          university={me.university}
          department={department || null}
          year={year}
          memberNo={me.id}
          verified={!!me.university}
        />

        {/* Fotoğraflar */}
        <section className="space-y-3">
          <h2 className="text-xl text-foreground">{t("profile.tabPhotos")}</h2>
          <div className="grid grid-cols-3 gap-2">
            {photos.map((photo, i) => (
              <div key={i} className="aspect-[3/4] rounded-xl overflow-hidden bg-muted relative">
                <img src={photo} alt="" className="w-full h-full object-cover" />
                <button
                  onClick={() => setPhotos(photos.filter((_, j) => j !== i))}
                  className="absolute top-1.5 right-1.5 w-7 h-7 rounded-full bg-background/90 text-foreground flex items-center justify-center hover:bg-background transition-colors"
                  title={t("pedit.removePhoto")}
                  aria-label={t("pedit.removePhoto")}
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
                <ImagePlus className={`w-7 h-7 text-muted-foreground ${uploading ? "animate-pulse" : ""}`} />
                <span className="text-[13px] font-semibold text-muted-foreground">
                  {t(uploading ? "ob.uploading" : "ob.addPhoto")}
                </span>
              </button>
            )}
          </div>
        </section>

        {/* Temel bilgiler */}
        <section className="space-y-3">
          <h2 className="text-xl text-foreground">{t("pedit.basics")}</h2>
          <Input
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder={t("pedit.namePlaceholder")}
            aria-label={t("card.name")}
            className="h-12"
          />
          {/* Üniversite e-postadan otomatik atanır; elle değiştirilemez */}
          <div className="rounded-xl border border-border bg-muted/50 px-4 py-3">
            <p className="text-[12px] text-muted-foreground">{t("ob.universityLabel")}</p>
            <p className="text-[15px] font-semibold text-foreground">
              {me.university ?? t("ob.universityUnknown")}
            </p>
          </div>
          <DepartmentPicker value={department} onChange={setDepartment} />
          <div className="flex gap-2">
            {[1, 2, 3, 4].map(y => (
              <button
                key={y}
                onClick={() => setYear(y)}
                aria-pressed={year === y}
                className={`flex-1 h-11 rounded-xl border text-[14px] font-semibold transition-colors ${choice(year === y)}`}
              >
                {t("ob.yearOption", { year: y })}
              </button>
            ))}
          </div>
        </section>

        {/* Bütçe */}
        <section className="space-y-4">
          <h2 className="text-xl text-foreground">{t("pedit.budget")}</h2>
          <p className="text-2xl font-semibold">
            <span className="marker">{n(budget[0])}–{n(budget[1])} ₺</span>
          </p>
          <Slider value={budget} onValueChange={setBudget} min={1000} max={50000} step={500} />
        </section>

        {/* Semtler */}
        <section className="space-y-3">
          <h2 className="text-xl text-foreground">{t("pedit.districts")}</h2>
          <div className="flex flex-wrap gap-2">
            {DISTRICTS.map(d => (
              <button
                key={d}
                onClick={() =>
                  setDistricts(prev => (prev.includes(d) ? prev.filter(x => x !== d) : [...prev, d]))
                }
                aria-pressed={districts.includes(d)}
                className={`h-9 px-3.5 rounded-full border text-[14px] font-semibold transition-colors ${choice(districts.includes(d))}`}
              >
                {d}
              </button>
            ))}
          </div>
        </section>

        {/* Yaşam tarzı */}
        <section className="space-y-3">
          <h2 className="text-xl text-foreground">{t("pedit.lifestyle")}</h2>
          {([
            { id: "smoking", key: "pedit.smoking", value: smoking, set: setSmoking },
            { id: "alcohol", key: "pedit.alcohol", value: alcohol, set: setAlcohol },
            { id: "pets", key: "pedit.pets", value: pets, set: setPets },
          ] as const).map(item => (
            <button
              key={item.id}
              role="checkbox"
              aria-checked={item.value}
              onClick={() => item.set(!item.value)}
              className="w-full flex items-center justify-between px-4 h-14 rounded-xl border border-input bg-card hover:border-foreground/40 transition-colors"
            >
              <span className="text-[15px] font-semibold text-foreground">{t(item.key)}</span>
              <span className={`w-6 h-6 rounded-md border flex items-center justify-center transition-colors ${item.value ? "bg-foreground border-foreground text-background" : "border-input"}`}>
                {item.value && <Check className="w-4 h-4" />}
              </span>
            </button>
          ))}
          <div className="flex gap-2 pt-1">
            {/* value'lar API sözleşmesi — çevrilmez, yalnızca etiketler çevrilir. */}
            {([
              { value: "erken", key: "pedit.sleepEarly" },
              { value: "gece", key: "pedit.sleepNight" },
              { value: "esnek", key: "pedit.sleepFlexible" },
            ] as const).map(s => (
              <button
                key={s.value}
                onClick={() => setSleep(s.value)}
                aria-pressed={sleep === s.value}
                className={`flex-1 h-11 rounded-xl border text-[14px] font-semibold transition-colors ${choice(sleep === s.value)}`}
              >
                {t(s.key)}
              </button>
            ))}
          </div>
        </section>

        {/* Bio */}
        <section className="space-y-3">
          <h2 className="text-xl text-foreground">{t("pedit.about")}</h2>
          <textarea
            value={bio}
            onChange={e => setBio(e.target.value)}
            rows={6}
            maxLength={2000}
            placeholder={t("pedit.bioPlaceholder")}
            aria-label={t("pedit.about")}
            style={{ backgroundAttachment: "local" }}
            className="paper-ruled w-full rounded-xl border border-input text-[15px] text-foreground placeholder:text-muted-foreground/80 outline-none resize-none transition-colors hover:border-foreground/30 focus-visible:border-secondary focus-visible:ring-[3px] focus-visible:ring-secondary/20"
          />
        </section>
      </div>

      {/* Kaydet */}
      <div className="fixed bottom-16 left-0 right-0 bg-background/95 backdrop-blur-md border-t border-border px-5 py-3">
        <div className="max-w-lg mx-auto">
          <Button
            size="lg"
            onClick={save}
            disabled={saving || name.trim().length === 0}
            className="w-full h-12 text-base disabled:opacity-40"
          >
            {t(saving ? "common.saving" : "common.save")}
          </Button>
        </div>
      </div>

      <BottomNav />
    </div>
  );
};

export default ProfileEdit;
