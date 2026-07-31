import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Mail, GraduationCap, ShieldCheck, Trash2, KeyRound, Calendar } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import PasswordInput from "@/components/PasswordInput";
import BottomNav from "@/components/layout/BottomNav";
import { useAuth } from "@/contexts/AuthContext";
import { changePassword, deleteAccount } from "@/lib/api";
import { parseUtc } from "@/lib/date";

const AccountSettings = () => {
  const navigate = useNavigate();
  const { user: me, logout } = useAuth();

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [saving, setSaving] = useState(false);

  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleting, setDeleting] = useState(false);

  if (!me) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-muted-foreground">Hesap ayarları için giriş yap</p>
      </div>
    );
  }

  const rules = {
    length: next.length >= 8,
    uppercase: /[A-Z]/.test(next),
    number: /[0-9]/.test(next),
  };
  const canSave =
    current.length > 0 && rules.length && rules.uppercase && rules.number && next === confirm;

  const submitPassword = async () => {
    setSaving(true);
    try {
      await changePassword(current, next);
      toast.success("Şifren güncellendi", {
        description: "Güvenlik için tüm oturumlar kapatıldı, tekrar giriş yap.",
      });
      logout();
      navigate("/login");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Şifre değiştirilemedi");
    } finally {
      setSaving(false);
    }
  };

  const submitDelete = async () => {
    setDeleting(true);
    try {
      await deleteAccount(deletePassword);
      toast.success("Hesabın silindi");
      logout();
      navigate("/");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Hesap silinemedi");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="min-h-screen bg-background pb-24">
      <div className="nav-header sticky top-0 z-50 px-6 py-4 flex items-center gap-3">
        <button
          onClick={() => navigate("/settings")}
          className="w-10 h-10 rounded-full bg-background flex items-center justify-center text-foreground hover:bg-muted transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <h1 className="text-lg font-bold text-foreground">Hesap Bilgileri</h1>
      </div>

      <div className="px-6 py-6 space-y-8 max-w-lg mx-auto">
        {/* Hesap özeti — değiştirilemeyen doğrulanmış alanlar */}
        <section className="space-y-3">
          <h2 className="text-sm font-bold text-foreground">Hesabın</h2>
          <div className="card-listing divide-y divide-border">
            {[
              { icon: Mail, label: "E-posta", value: me.email },
              {
                icon: GraduationCap,
                label: "Üniversite",
                value: me.university ?? "E-posta alan adından belirlenemedi",
              },
              {
                icon: Calendar,
                label: "Üyelik",
                value: parseUtc(me.created_at).toLocaleDateString("tr-TR", {
                  day: "numeric",
                  month: "long",
                  year: "numeric",
                }),
              },
            ].map(row => (
              <div key={row.label} className="flex items-center gap-3 p-4">
                <row.icon className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                <div className="min-w-0">
                  <p className="text-[11px] text-muted-foreground">{row.label}</p>
                  <p className="text-sm text-foreground truncate">{row.value}</p>
                </div>
              </div>
            ))}
          </div>
          <p className="text-[11px] text-muted-foreground flex items-start gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 mt-px flex-shrink-0 text-accent" />
            E-posta ve üniversite doğrulanmış kimlik bilgilerindir, değiştirilemez.
            Profilinin geri kalanını{" "}
            <button onClick={() => navigate("/profile/edit")} className="underline">
              Profili Düzenle
            </button>{" "}
            sayfasından güncelleyebilirsin.
          </p>
        </section>

        {/* Şifre değiştirme */}
        <section className="space-y-3">
          <h2 className="text-sm font-bold text-foreground flex items-center gap-2">
            <KeyRound className="w-4 h-4" /> Şifre Değiştir
          </h2>
          <PasswordInput
            value={current}
            onChange={e => setCurrent(e.target.value)}
            placeholder="Mevcut şifren"
            autoComplete="current-password"
            className="h-12 rounded-xl"
          />
          <PasswordInput
            value={next}
            onChange={e => setNext(e.target.value)}
            placeholder="Yeni şifre"
            className="h-12 rounded-xl"
          />
          {next.length > 0 && (
            <div className="space-y-1">
              {[
                { ok: rules.length, text: "En az 8 karakter" },
                { ok: rules.uppercase, text: "En az 1 büyük harf" },
                { ok: rules.number, text: "En az 1 rakam" },
              ].map(r => (
                <p key={r.text} className={`text-xs ${r.ok ? "text-accent" : "text-muted-foreground"}`}>
                  {r.ok ? "✓" : "○"} {r.text}
                </p>
              ))}
            </div>
          )}
          <PasswordInput
            value={confirm}
            onChange={e => setConfirm(e.target.value)}
            placeholder="Yeni şifre (tekrar)"
            className="h-12 rounded-xl"
          />
          {confirm.length > 0 && next !== confirm && (
            <p className="text-xs text-destructive">Şifreler eşleşmiyor</p>
          )}
          <Button
            onClick={submitPassword}
            disabled={!canSave || saving}
            className="w-full h-12 rounded-full font-bold disabled:opacity-50"
          >
            {saving ? "Kaydediliyor…" : "Şifreyi Güncelle"}
          </Button>
          <p className="text-[11px] text-muted-foreground">
            Şifre değişince güvenlik için tüm cihazlardaki oturumlar kapatılır.
          </p>
        </section>

        {/* Tehlikeli bölge */}
        <section className="space-y-3">
          <h2 className="text-sm font-bold text-destructive flex items-center gap-2">
            <Trash2 className="w-4 h-4" /> Hesabı Sil
          </h2>
          <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-4 space-y-3">
            <p className="text-xs text-muted-foreground">
              Hesabın, ilanların, eşleşmelerin ve mesajların kalıcı olarak silinir.
              Bu işlem geri alınamaz.
            </p>
            {!deleteOpen ? (
              <Button
                variant="outline"
                onClick={() => setDeleteOpen(true)}
                className="w-full h-11 rounded-full border-destructive/40 text-destructive hover:bg-destructive hover:text-destructive-foreground"
              >
                Hesabımı silmek istiyorum
              </Button>
            ) : (
              <div className="space-y-3">
                <PasswordInput
                  value={deletePassword}
                  onChange={e => setDeletePassword(e.target.value)}
                  placeholder="Onaylamak için şifreni gir"
                  className="h-12 rounded-xl"
                />
                <div className="flex gap-2">
                  <Button
                    variant="ghost"
                    onClick={() => { setDeleteOpen(false); setDeletePassword(""); }}
                    className="flex-1 h-11 rounded-full"
                  >
                    Vazgeç
                  </Button>
                  <Button
                    onClick={submitDelete}
                    disabled={deletePassword.length === 0 || deleting}
                    className="flex-1 h-11 rounded-full bg-destructive text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50"
                  >
                    {deleting ? "Siliniyor…" : "Kalıcı olarak sil"}
                  </Button>
                </div>
              </div>
            )}
          </div>
        </section>
      </div>

      <BottomNav />
    </div>
  );
};

export default AccountSettings;
