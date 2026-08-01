import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Check, X, ImagePlus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import BottomNav from "@/components/layout/BottomNav";
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

  return (
    <div className="min-h-screen bg-background pb-32">
      {/* Header */}
      <div className="nav-header sticky top-0 z-50 px-6 py-4 flex items-center gap-3">
        <button
          onClick={() => navigate("/profile")}
          className="w-10 h-10 rounded-full bg-background flex items-center justify-center text-foreground hover:bg-muted transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <h1 className="text-lg font-bold text-foreground">{t("pedit.title")}</h1>
      </div>

      <div className="px-6 py-6 space-y-8 max-w-lg mx-auto">
        {/* Fotoğraflar */}
        <section className="space-y-3">
          <h2 className="text-sm font-bold text-foreground">{t("profile.tabPhotos")}</h2>
          <div className="grid grid-cols-3 gap-3">
            {photos.map((photo, i) => (
              <div key={i} className="aspect-square rounded-2xl overflow-hidden border-2 border-border relative group">
                <img src={photo} alt="" className="w-full h-full object-cover" />
                <button
                  onClick={() => setPhotos(photos.filter((_, j) => j !== i))}
                  className="absolute top-2 right-2 w-6 h-6 rounded-full bg-destructive/90 flex items-center justify-center"
                  title={t("pedit.removePhoto")}
                  aria-label={t("pedit.removePhoto")}
                >
                  <X className="w-3 h-3 text-destructive-foreground" />
                </button>
              </div>
            ))}
            {photos.length < 6 && (
              <button
                onClick={() => pickPhoto(6 - photos.length)}
                disabled={uploading}
                className="aspect-square rounded-2xl border-2 border-dashed border-muted-foreground/30 flex flex-col items-center justify-center gap-2 bg-card hover:border-primary/40 transition-all disabled:opacity-50"
              >
                <ImagePlus className={`w-7 h-7 text-muted-foreground ${uploading ? "animate-pulse" : ""}`} />
                <span className="text-xs text-muted-foreground">
                  {t(uploading ? "ob.uploading" : "ob.addPhoto")}
                </span>
              </button>
            )}
          </div>
        </section>

        {/* Temel bilgiler */}
        <section className="space-y-3">
          <h2 className="text-sm font-bold text-foreground">{t("pedit.basics")}</h2>
          <Input
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder={t("pedit.namePlaceholder")}
            className="h-12 rounded-xl"
          />
          {/* Üniversite e-postadan otomatik atanır; elle değiştirilemez */}
          <div className="rounded-xl border border-border bg-muted/40 px-4 py-3">
            <p className="text-[10px] text-muted-foreground">{t("ob.universityLabel")}</p>
            <p className="text-sm font-medium text-foreground">
              {me.university ?? t("ob.universityUnknown")}
            </p>
          </div>
          <DepartmentPicker value={department} onChange={setDepartment} />
          <div className="flex gap-2">
            {[1, 2, 3, 4].map(y => (
              <button
                key={y}
                onClick={() => setYear(y)}
                className={`flex-1 py-2.5 rounded-xl border-2 text-sm font-bold transition-all ${
                  year === y ? "border-secondary bg-lavender/30" : "border-border bg-card hover:border-primary/30"
                }`}
              >
                {t("ob.yearOption", { year: y })}
              </button>
            ))}
          </div>
        </section>

        {/* Bütçe */}
        <section className="space-y-4">
          <h2 className="text-sm font-bold text-foreground">{t("pedit.budget")}</h2>
          <p className="text-center text-xl font-bold text-foreground tabular-nums">
            {n(budget[0])} — {n(budget[1])} {t("common.currency")}
          </p>
          <Slider value={budget} onValueChange={setBudget} min={1000} max={50000} step={500} />
        </section>

        {/* Semtler */}
        <section className="space-y-3">
          <h2 className="text-sm font-bold text-foreground">{t("pedit.districts")}</h2>
          <div className="flex flex-wrap gap-2">
            {DISTRICTS.map(d => (
              <button
                key={d}
                onClick={() =>
                  setDistricts(prev => (prev.includes(d) ? prev.filter(x => x !== d) : [...prev, d]))
                }
                className={`px-3.5 py-2 rounded-full text-sm font-medium transition-all ${
                  districts.includes(d)
                    ? "bg-primary text-primary-foreground"
                    : "bg-card border border-border text-foreground hover:border-primary/40"
                }`}
              >
                {d}
              </button>
            ))}
          </div>
        </section>

        {/* Yaşam tarzı */}
        <section className="space-y-3">
          <h2 className="text-sm font-bold text-foreground">{t("pedit.lifestyle")}</h2>
          {([
            { id: "smoking", key: "pedit.smoking", value: smoking, set: setSmoking },
            { id: "alcohol", key: "pedit.alcohol", value: alcohol, set: setAlcohol },
            { id: "pets", key: "pedit.pets", value: pets, set: setPets },
          ] as const).map(item => (
            <button
              key={item.id}
              onClick={() => item.set(!item.value)}
              className={`w-full flex items-center justify-between p-4 rounded-xl border-2 transition-all ${
                item.value ? "border-primary bg-primary/5" : "border-border bg-card"
              }`}
            >
              <span className="text-sm font-medium text-foreground">{t(item.key)}</span>
              <div className={`w-6 h-6 rounded-full flex items-center justify-center ${item.value ? "bg-primary" : "bg-muted"}`}>
                {item.value && <Check className="w-4 h-4 text-primary-foreground" />}
              </div>
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
                className={`flex-1 py-2.5 rounded-xl border-2 text-sm font-medium transition-all ${
                  sleep === s.value ? "border-secondary bg-lavender/30" : "border-border bg-card"
                }`}
              >
                {t(s.key)}
              </button>
            ))}
          </div>
        </section>

        {/* Bio */}
        <section className="space-y-3">
          <h2 className="text-sm font-bold text-foreground">{t("pedit.about")}</h2>
          <textarea
            value={bio}
            onChange={e => setBio(e.target.value)}
            rows={4}
            maxLength={2000}
            placeholder={t("pedit.bioPlaceholder")}
            className="w-full rounded-xl bg-card border border-border px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground outline-none focus:ring-2 focus:ring-primary/20 resize-none"
          />
        </section>
      </div>

      {/* Kaydet */}
      <div className="fixed bottom-16 left-0 right-0 bg-card/80 backdrop-blur-lg p-4">
        <div className="max-w-lg mx-auto">
          <Button
            onClick={save}
            disabled={saving || name.trim().length === 0}
            className="w-full h-12 rounded-full bg-primary text-primary-foreground font-bold disabled:opacity-50"
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
