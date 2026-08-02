import { useEffect, useId, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BedDouble, ChevronLeft, ChevronRight, DollarSign, Home, MapPin,
  MessageCircle, RefreshCw, Search, ShieldAlert, X,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import BottomNav from "@/components/layout/BottomNav";
import AppHeader from "@/components/layout/AppHeader";
import FairPriceBadge from "@/components/FairPriceBadge";
import LocationPicker, { type LocationValue } from "@/components/LocationPicker";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/i18n";
import type { TranslationKey } from "@/i18n/translations";
import { parseUtc } from "@/lib/date";
import {
  LISTING_FEATURES,
  adminDeleteListing,
  adminPublishListing,
  adminUpdateListing,
  fetchAdminListings,
  postSwipe,
  restoreRemoved,
  reviewFlagged,
  type AdminListing,
  type AdminListingStatus,
  type AdminListingUpdate,
  type ListingFeature,
  type RestoreResult,
} from "@/lib/api";

/**
 * İlan yönetimi sayfası — yalnızca yöneticiye açıktır.
 *
 * Normal `GET /api/listings` tasarımı gereği yalnız yayındaki ve sahibi askıda
 * OLMAYAN ilanları döner; bu sayfa `GET /api/admin/listings` kullanır çünkü
 * yöneticinin bakması gereken kayıtlar tam da o filtrenin gizledikleridir.
 */

// Sunucu ilan listesini 1-200 arası sayfalar; 50 varsayılan sayfa boyutu.
const PAGE_SIZE = 50;
// Sunucu not/sebep alanlarını en fazla 500 karakter kabul eder.
const NOTE_MAX = 500;
// ListingUpdate sınırları (backend/app/listings.py).
const TITLE_MIN = 3;
const TITLE_MAX = 120;
const DESC_MAX = 2000;
const ROOM_MAX = 10;

// Ev özelliği -> etiket anahtarı (FilterModal'daki çiplerle aynı anahtarlar).
const featureLabels: Record<ListingFeature, TranslationKey> = {
  furnished: "filter.furnished",
  elevator: "filter.elevator",
  parking: "filter.parking",
  internet_included: "filter.internet",
  heating_included: "filter.heating",
  balcony: "filter.balcony",
  natural_gas: "filter.gas",
};

/** İlanda açıkça true olan özellikler; null ("bilinmiyor") gösterilmez. */
const listingFeatures = (l: AdminListing): ListingFeature[] =>
  LISTING_FEATURES.filter(key => l[key] === true);

const isHouse = (l: AdminListing) => l.type === "ev_ilani";

/**
 * Fiyat metni. Tanımadığımız bir tip gelirse (sunucu `type`'ı bilerek serbest
 * bırakıyor, bkz. AdminListing) fiyat uydurmak yerine tire basılır.
 */
const priceLabel = (l: AdminListing, n: (v: number) => string): string => {
  if (isHouse(l)) return l.rent == null ? "—" : `${n(l.rent)} ₺`;
  if (l.type === "kisisel_ilan") {
    if (l.budget_min == null || l.budget_max == null) return "—";
    return `${n(l.budget_min)}–${n(l.budget_max)} ₺`;
  }
  return "—";
};

const fmtDate = (iso: string, locale: string) =>
  parseUtc(iso).toLocaleDateString(locale, { day: "numeric", month: "short", year: "numeric" });

// ---- küçük ortak parçalar ----

const Chip = ({
  children,
  tone = "muted",
}: {
  children: React.ReactNode;
  tone?: "muted" | "warn" | "danger" | "ok";
}) => {
  const tones = {
    muted: "bg-muted text-muted-foreground",
    warn: "bg-sand text-foreground",
    danger: "bg-destructive/10 text-destructive",
    ok: "bg-lavender/50 text-foreground",
  } as const;
  return (
    <span className={`inline-block text-[10px] px-2.5 py-1 rounded-full font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
};

const ActionButton = ({
  label,
  onClick,
  destructive = false,
  disabled = false,
}: {
  label: string;
  onClick: () => void;
  destructive?: boolean;
  disabled?: boolean;
}) => (
  <button
    type="button"
    onClick={onClick}
    disabled={disabled}
    className={`h-9 px-4 rounded-full text-xs font-bold transition-all active:scale-95 disabled:opacity-50 disabled:pointer-events-none ${
      destructive
        ? "bg-destructive/10 text-destructive hover:bg-destructive hover:text-destructive-foreground"
        : "bg-primary/10 text-primary hover:bg-primary hover:text-primary-foreground"
    }`}
  >
    {label}
  </button>
);

// ---- onay penceresi ----

/**
 * Yıkıcı/kalıcı eylemler için onay penceresi. Deseni AdminActionDialog ile
 * aynıdır (elle kurulmuş panel + odak tuzağı + Esc); farkı, bu sayfanın üç
 * eylemini tek bileşenle karşılayacak kadar genel olması.
 *
 * `input === "reason"` iken boş metinle onaylanamaz: kalıcı silmede gerekçe
 * sunucuda da zorunludur (422) ve denetim kaydına yazılacak tek açıklamadır.
 */
const ConfirmDialog = ({
  open,
  title,
  desc,
  warning = null,
  input,
  inputLabel,
  inputPlaceholder,
  destructive = false,
  pending = false,
  error = null,
  onClose,
  onConfirm,
}: {
  open: boolean;
  title: string;
  desc: string;
  warning?: string | null;
  input: "none" | "note" | "reason";
  inputLabel: string;
  inputPlaceholder: string;
  destructive?: boolean;
  pending?: boolean;
  error?: string | null;
  onClose: () => void;
  onConfirm: (note: string) => void;
}) => {
  const { t } = useI18n();
  const [note, setNote] = useState("");
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  // Kapanışta odak, eylemi başlatan düğmeye geri döner.
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const headingId = useId();

  // Her açılışta temiz başla — önceki eylemin gerekçesi yenisine taşınmasın.
  useEffect(() => {
    if (!open) return;
    setNote("");
    returnFocusRef.current = document.activeElement as HTMLElement | null;
    const id = window.setTimeout(() => closeRef.current?.focus(), 0);
    return () => {
      window.clearTimeout(id);
      returnFocusRef.current?.focus?.();
    };
  }, [open, title]);

  // Esc ile kapanma + odağın panel içinde dönmesi (basit tuzak).
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== "Tab" || !panelRef.current) return;
      const focusables = panelRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), textarea, [href], input, select, [tabindex]:not([tabindex="-1"])',
      );
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && (active === first || !panelRef.current.contains(active))) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown, true);
    return () => document.removeEventListener("keydown", onKeyDown, true);
  }, [open, onClose]);

  const blocked = pending || (input === "reason" && note.trim().length === 0);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm"
          onClick={pending ? undefined : onClose}
        >
          <motion.div
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={headingId}
            initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.95, opacity: 0 }}
            className="bg-card rounded-2xl shadow-2xl w-full max-w-[440px] max-h-[85vh] flex flex-col"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-start gap-3 px-6 py-4 border-b border-border">
              <div
                className={`w-9 h-9 rounded-2xl flex items-center justify-center shrink-0 ${
                  destructive ? "bg-destructive/10" : "bg-primary/10"
                }`}
              >
                <ShieldAlert className={`w-4 h-4 ${destructive ? "text-destructive" : "text-primary"}`} />
              </div>
              <div className="flex-1 min-w-0">
                <h2 id={headingId} className="text-base font-bold text-foreground">{title}</h2>
              </div>
              <button
                ref={closeRef}
                type="button"
                onClick={onClose}
                aria-label={t("common.close")}
                className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-foreground hover:bg-muted/80 shrink-0"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
              <p className="text-sm text-muted-foreground">{desc}</p>

              {warning && (
                <div className="rounded-2xl border border-destructive/30 bg-destructive/5 px-4 py-3">
                  <p className="text-xs text-destructive">{warning}</p>
                </div>
              )}

              {input !== "none" && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-bold text-foreground">{inputLabel}</h3>
                    <span className="text-[11px] text-muted-foreground tabular-nums">
                      {t("report.noteCounter", { count: note.length, max: NOTE_MAX })}
                    </span>
                  </div>
                  <Textarea
                    value={note}
                    // Sunucu 500'ün üstünü 422 ile reddeder; girişte kırpıyoruz.
                    onChange={e => setNote(e.target.value.slice(0, NOTE_MAX))}
                    maxLength={NOTE_MAX}
                    placeholder={inputPlaceholder}
                    className="rounded-2xl min-h-[96px] resize-none"
                  />
                </div>
              )}

              {error && (
                <div className="rounded-2xl border border-destructive/30 bg-destructive/5 px-4 py-3">
                  <p className="text-xs text-destructive">{error}</p>
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-border">
              <Button
                variant="ghost"
                onClick={onClose}
                disabled={pending}
                className="rounded-full h-11 px-5 text-sm font-medium"
              >
                {t("common.cancel")}
              </Button>
              <Button
                onClick={() => onConfirm(note)}
                disabled={blocked}
                className={`rounded-full h-11 px-6 text-sm font-bold ${
                  destructive ? "bg-destructive text-destructive-foreground hover:bg-destructive/90" : ""
                }`}
              >
                {pending ? t("admin.dlgWorking") : t("admin.dlgConfirm")}
              </Button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

// ---- düzenleme ----

/** Düzenleme formunun o anki hâli; tüm sayısal alanlar metin tutulur. */
export interface ListingEditForm {
  title: string;
  description: string;
  location: LocationValue;
  rent: string;
  roomCount: string;
  features: Record<ListingFeature, boolean>;
  budgetMin: string;
  budgetMax: string;
}

export const formFromListing = (l: AdminListing): ListingEditForm => ({
  title: l.title,
  description: l.description,
  location: { district: l.district ?? "", neighborhood: l.neighborhood ?? "" },
  rent: l.rent == null ? "" : String(l.rent),
  roomCount: l.room_count ?? "",
  // Kutu "açıkça true" demektir; null ("bilinmiyor") işaretsiz görünür ve
  // dokunulmadığı sürece null kalır (bkz. buildListingPatch).
  features: Object.fromEntries(
    LISTING_FEATURES.map(key => [key, l[key] === true]),
  ) as Record<ListingFeature, boolean>,
  budgetMin: l.budget_min == null ? "" : String(l.budget_min),
  budgetMax: l.budget_max == null ? "" : String(l.budget_max),
});

/**
 * Formun ilk hâlinden SAPMAYAN hiçbir alan gönderilmez.
 *
 * Bu bir üslup tercihi değil, veri koruma kuralı: sunucu PATCH gövdesinde
 * gelen her alanı yazar ve ev özellikleri üç değerlidir (true / false /
 * null = "bilinmiyor"). Tüm kutuları toptan göndermek, sahibinin hiç
 * belirtmediği özellikleri sessizce "yok" (false) yapardı. Kutu işaretsizken
 * karşılaştırma `l[key] === true` ile yapıldığı için null alan dokunulmadığı
 * sürece null kalır.
 *
 * Saf fonksiyondur — bileşenden ayrı test edilir.
 */
export const buildListingPatch = (l: AdminListing, f: ListingEditForm): AdminListingUpdate => {
  const patch: AdminListingUpdate = {};

  const title = f.title.trim();
  if (title !== l.title) patch.title = title;

  const description = f.description.trim();
  if (description !== l.description) patch.description = description;

  if (f.location.district !== l.district) patch.district = f.location.district;

  if (isHouse(l)) {
    if (f.location.neighborhood !== (l.neighborhood ?? "")) {
      patch.neighborhood = f.location.neighborhood;
    }
    const rent = Number(f.rent.trim());
    if (f.rent.trim() !== "" && Number.isFinite(rent) && rent !== l.rent) patch.rent = rent;

    const rooms = f.roomCount.trim();
    if (rooms !== (l.room_count ?? "")) patch.room_count = rooms;

    const features: Partial<Record<ListingFeature, boolean>> = {};
    for (const key of LISTING_FEATURES) {
      if (f.features[key] !== (l[key] === true)) features[key] = f.features[key];
    }
    Object.assign(patch, features);
  } else {
    const min = Number(f.budgetMin.trim());
    if (f.budgetMin.trim() !== "" && Number.isFinite(min) && min !== l.budget_min) {
      patch.budget_min = min;
    }
    const max = Number(f.budgetMax.trim());
    if (f.budgetMax.trim() !== "" && Number.isFinite(max) && max !== l.budget_max) {
      patch.budget_max = max;
    }
  }

  return patch;
};

/**
 * Sunucunun reddedeceği gövdeyi hiç yollamamak için ön doğrulama. Sunucu tek
 * doğruluk kaynağıdır (422 metni yine gösterilir); buradaki amaç yöneticiye
 * hatayı alan başındayken söylemek. İlk hatanın anahtarını döndürür.
 */
export const validateListingForm = (
  l: AdminListing,
  f: ListingEditForm,
): TranslationKey | null => {
  const title = f.title.trim();
  if (title.length < TITLE_MIN || title.length > TITLE_MAX) return "listings.errTitle";

  const description = f.description.trim();
  if (description.length === 0 || description.length > DESC_MAX) return "listings.errDescription";

  if (!f.location.district) return "listings.errDistrict";

  if (isHouse(l)) {
    const raw = f.rent.trim();
    if (raw !== "") {
      const rent = Number(raw);
      if (!Number.isFinite(rent) || rent <= 0) return "listings.errRent";
    }
    return null;
  }

  // Kişisel ilan: boş bırakılan alan "dokunma" demektir, kayıttaki değer geçerli
  // kalır — sınır karşılaştırması bu yüzden ETKİN değerlerle yapılır.
  const rawMin = f.budgetMin.trim();
  const rawMax = f.budgetMax.trim();
  for (const raw of [rawMin, rawMax]) {
    if (raw === "") continue;
    const value = Number(raw);
    if (!Number.isFinite(value) || value <= 0) return "listings.errBudgetValue";
  }
  const min = rawMin === "" ? l.budget_min : Number(rawMin);
  const max = rawMax === "" ? l.budget_max : Number(rawMax);
  if (min != null && max != null && min > max) return "listings.errBudget";
  return null;
};

const FieldLabel = ({ children }: { children: React.ReactNode }) => (
  <h3 className="text-sm font-bold text-foreground mb-2">{children}</h3>
);

/**
 * Düzenleme penceresi. Yeni bir ilan formu değildir: mevcut alanları sade bir
 * pencerede toplar ve YALNIZCA değişenleri gönderir.
 */
const EditDialog = ({
  listing,
  pending,
  error,
  onClose,
  onSave,
}: {
  listing: AdminListing | null;
  pending: boolean;
  error: string | null;
  onClose: () => void;
  onSave: (patch: AdminListingUpdate) => void;
}) => {
  const { t } = useI18n();
  const [form, setForm] = useState<ListingEditForm | null>(null);
  const [localError, setLocalError] = useState<TranslationKey | null>(null);
  const headingId = useId();

  // Pencere her açıldığında form kaydın GÜNCEL hâlinden kurulur.
  useEffect(() => {
    setLocalError(null);
    setForm(listing ? formFromListing(listing) : null);
  }, [listing]);

  useEffect(() => {
    if (!listing) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !pending) {
        e.stopPropagation();
        onClose();
      }
    };
    document.addEventListener("keydown", onKeyDown, true);
    return () => document.removeEventListener("keydown", onKeyDown, true);
  }, [listing, pending, onClose]);

  if (!listing || !form) return null;

  const house = isHouse(listing);
  const patch = buildListingPatch(listing, form);
  const changedCount = Object.keys(patch).length;
  const set = (partial: Partial<ListingEditForm>) => setForm({ ...form, ...partial });

  const submit = () => {
    const problem = validateListingForm(listing, form);
    setLocalError(problem);
    if (problem) return;
    onSave(patch);
  };

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm"
        onClick={pending ? undefined : onClose}
      >
        <motion.div
          role="dialog"
          aria-modal="true"
          aria-labelledby={headingId}
          initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.95, opacity: 0 }}
          className="bg-card rounded-2xl shadow-2xl w-full max-w-[520px] max-h-[88vh] flex flex-col"
          onClick={e => e.stopPropagation()}
        >
          <div className="flex items-start gap-3 px-6 py-4 border-b border-border">
            <div className="flex-1 min-w-0">
              <h2 id={headingId} className="text-base font-bold text-foreground">
                {t("listings.dlgEditTitle")}
              </h2>
              <p className="text-xs text-muted-foreground truncate">{listing.title}</p>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label={t("common.close")}
              className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-foreground hover:bg-muted/80 shrink-0"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
            <p className="text-sm text-muted-foreground">{t("listings.dlgEditDesc")}</p>

            <div>
              <FieldLabel>{t("listings.fieldTitle")}</FieldLabel>
              <Input
                value={form.title}
                onChange={e => set({ title: e.target.value.slice(0, TITLE_MAX) })}
                maxLength={TITLE_MAX}
                className="rounded-2xl"
              />
            </div>

            <div>
              <FieldLabel>{t("listings.fieldDescription")}</FieldLabel>
              <Textarea
                value={form.description}
                onChange={e => set({ description: e.target.value.slice(0, DESC_MAX) })}
                maxLength={DESC_MAX}
                className="rounded-2xl min-h-[120px] resize-none"
              />
            </div>

            {/* Kişisel ilanda mahalle hiç sorulmaz (ilan oluşturma akışıyla aynı). */}
            <LocationPicker
              value={form.location}
              onChange={location => set({ location })}
              districtOnly={!house}
            />

            {house ? (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <FieldLabel>{t("listings.fieldRent")}</FieldLabel>
                    <Input
                      type="number"
                      inputMode="numeric"
                      min={1}
                      value={form.rent}
                      onChange={e => set({ rent: e.target.value })}
                      className="rounded-2xl"
                    />
                  </div>
                  <div>
                    <FieldLabel>{t("listings.fieldRooms")}</FieldLabel>
                    <Input
                      value={form.roomCount}
                      onChange={e => set({ roomCount: e.target.value.slice(0, ROOM_MAX) })}
                      maxLength={ROOM_MAX}
                      placeholder="2+1"
                      className="rounded-2xl"
                    />
                  </div>
                </div>

                <div>
                  <FieldLabel>{t("listings.fieldFeatures")}</FieldLabel>
                  <div className="flex flex-wrap gap-2">
                    {LISTING_FEATURES.map(key => {
                      const on = form.features[key];
                      return (
                        <button
                          key={key}
                          type="button"
                          aria-pressed={on}
                          onClick={() => set({ features: { ...form.features, [key]: !on } })}
                          className={`px-3 py-1.5 rounded-full text-[11px] font-medium transition-all ${
                            on
                              ? "bg-primary text-primary-foreground"
                              : "bg-card border border-border text-foreground hover:border-primary/30"
                          }`}
                        >
                          {t(featureLabels[key])}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <FieldLabel>{t("listings.fieldBudgetMin")}</FieldLabel>
                  <Input
                    type="number"
                    inputMode="numeric"
                    min={1}
                    value={form.budgetMin}
                    onChange={e => set({ budgetMin: e.target.value })}
                    className="rounded-2xl"
                  />
                </div>
                <div>
                  <FieldLabel>{t("listings.fieldBudgetMax")}</FieldLabel>
                  <Input
                    type="number"
                    inputMode="numeric"
                    min={1}
                    value={form.budgetMax}
                    onChange={e => set({ budgetMax: e.target.value })}
                    className="rounded-2xl"
                  />
                </div>
              </div>
            )}

            {(localError || error) && (
              <div className="rounded-2xl border border-destructive/30 bg-destructive/5 px-4 py-3">
                <p className="text-xs text-destructive">{localError ? t(localError) : error}</p>
              </div>
            )}
          </div>

          <div className="flex items-center justify-between gap-3 px-6 py-4 border-t border-border">
            <p className="text-[11px] text-muted-foreground">
              {changedCount === 0 ? t("listings.editNoChange") : t("listings.editChangedCount", { count: changedCount })}
            </p>
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                onClick={onClose}
                disabled={pending}
                className="rounded-full h-11 px-5 text-sm font-medium"
              >
                {t("common.cancel")}
              </Button>
              <Button
                onClick={submit}
                disabled={pending || changedCount === 0}
                className="rounded-full h-11 px-6 text-sm font-bold"
              >
                {pending ? t("common.saving") : t("common.save")}
              </Button>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

// ---- ilan satırı ----

/** Onay penceresinden geçen eylemler; "publish" doğrudan çalışır (geri alınabilir). */
type DialogAction =
  | { kind: "unpublish"; listing: AdminListing }
  | { kind: "restore"; listing: AdminListing }
  | { kind: "delete"; listing: AdminListing };

const ListingRow = ({
  listing,
  busy,
  onDetails,
  onEdit,
  onPublish,
  onAction,
}: {
  listing: AdminListing;
  busy: boolean;
  onDetails: () => void;
  onEdit: () => void;
  onPublish: () => void;
  onAction: (a: DialogAction) => void;
}) => {
  const { t, n, locale } = useI18n();
  const removed = listing.moderation_removed;
  const typeLabel =
    listing.type === "ev_ilani"
      ? t("profile.house")
      : listing.type === "kisisel_ilan"
        ? t("profile.personal")
        : listing.type;

  return (
    <div className="card-listing p-4 space-y-3">
      <div className="flex gap-3">
        <div className="w-24 h-20 shrink-0 rounded-xl overflow-hidden bg-muted">
          {listing.photos[0] ? (
            <img src={listing.photos[0]} alt="" className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <Home className="w-6 h-6 text-muted-foreground" />
            </div>
          )}
        </div>

        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex flex-wrap items-center gap-1.5">
            {/* Durum tek çiple anlatılır: kaldırılan ilan da pasiftir ama
                kararın SAHİBİNDEN mi YÖNETİCİDEN mi geldiği ayrı şeydir. */}
            {removed ? (
              <Chip tone="danger">{t("listings.statusRemoved")}</Chip>
            ) : listing.is_active ? (
              <Chip tone="ok">{t("listings.statusActive")}</Chip>
            ) : (
              <Chip tone="warn">{t("listings.statusInactive")}</Chip>
            )}
            {listing.is_flagged && <Chip tone="warn">{t("admin.badgeFlagged")}</Chip>}
            {listing.owner_suspended && <Chip tone="danger">{t("listings.badgeOwnerSuspended")}</Chip>}
            <Chip>{typeLabel}</Chip>
          </div>

          <p className="font-bold text-[15px] text-foreground break-words">{listing.title}</p>

          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <MapPin className="w-3 h-3" /> {listing.district}
              {listing.neighborhood ? ` · ${listing.neighborhood}` : ""}
            </span>
            {listing.room_count && <span>· {listing.room_count}</span>}
            <span>·</span>
            <span className="font-bold text-accent">{priceLabel(listing, n)}</span>
          </div>

          <p className="text-xs text-muted-foreground break-words">
            {listing.owner_name
              ? t("admin.ownerLabel", { name: listing.owner_name })
              : t("listings.ownerUnknown")}{" "}
            · {t("listings.createdAt", { date: fmtDate(listing.created_at, locale) })}
          </p>
        </div>
      </div>

      {/* Yayında görünen ama kimsenin göremediği ilan: sessiz kalmak yanıltıcı olur. */}
      {listing.is_active && listing.owner_suspended && (
        <div className="rounded-2xl border border-destructive/30 bg-destructive/5 px-3 py-2">
          <p className="text-xs text-destructive">{t("listings.hiddenNote")}</p>
        </div>
      )}

      {removed && listing.review_note && (
        <div>
          <p className="text-[11px] font-semibold text-foreground">{t("admin.resolutionNote")}</p>
          <p className="text-sm text-muted-foreground break-words">{listing.review_note}</p>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <ActionButton label={t("common.edit")} onClick={onEdit} disabled={busy} />

        {/* Yönetici kaldırmasının geri alma yolu ayrıdır: yayına alma ucu bu
            kayda dokunmaz (409). İki uç aynı alanı iki kuralla yazmasın. */}
        {removed ? (
          <ActionButton
            label={t("admin.actionRestore")}
            onClick={() => onAction({ kind: "restore", listing })}
            disabled={busy}
          />
        ) : listing.is_active ? (
          <ActionButton
            destructive
            label={t("listings.actionUnpublish")}
            onClick={() => onAction({ kind: "unpublish", listing })}
            disabled={busy}
          />
        ) : (
          <ActionButton label={t("listings.actionPublish")} onClick={onPublish} disabled={busy} />
        )}

        <ActionButton
          destructive
          label={t("listings.actionDelete")}
          onClick={() => onAction({ kind: "delete", listing })}
          disabled={busy}
        />

        <button
          type="button"
          onClick={onDetails}
          className="h-9 px-2 text-xs text-primary font-medium hover:underline"
        >
          {t("listings.details")}
        </button>
      </div>
    </div>
  );
};

// ---- sayfa ----

const STATUS_OPTIONS: { value: AdminListingStatus; key: TranslationKey }[] = [
  { value: "all", key: "listings.filterAll" },
  { value: "active", key: "listings.statusActive" },
  { value: "inactive", key: "listings.statusInactive" },
  { value: "removed", key: "listings.statusRemoved" },
  { value: "flagged", key: "listings.statusFlagged" },
];

const Listings = () => {
  const navigate = useNavigate();
  const { user: viewer } = useAuth();
  const { t, n } = useI18n();
  const queryClient = useQueryClient();

  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<AdminListingStatus>("all");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<AdminListing | null>(null);
  const [editing, setEditing] = useState<AdminListing | null>(null);
  const [editError, setEditError] = useState<string | null>(null);
  const [action, setAction] = useState<DialogAction | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const isAdmin = viewer?.is_admin === true;

  // Her tuşta istek atmamak için kısa gecikme; arama sunucuda çalışıyor.
  useEffect(() => {
    const id = window.setTimeout(() => setQuery(search.trim()), 300);
    return () => window.clearTimeout(id);
  }, [search]);

  // Süzgeç değişince ilk sayfaya dön: aksi hâlde 3. sayfada boş liste görünür.
  useEffect(() => setPage(0), [query, status]);

  const listQuery = useQuery({
    queryKey: ["admin", "listings", query, status, page],
    queryFn: () =>
      fetchAdminListings({
        q: query || undefined,
        status,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      }),
    enabled: isAdmin,
  });

  const rows = listQuery.data ?? [];

  /** Panelin listeleri + genel ilan listesi tazelensin. */
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["admin"] });
    queryClient.invalidateQueries({ queryKey: ["listings"] });
  };

  const failed = (err: unknown) => {
    const message = err instanceof Error ? err.message : t("common.error");
    toast.error(t("admin.actionFailed"), { description: message });
    return message;
  };

  const publishMutation = useMutation({
    mutationFn: (id: number) => adminPublishListing(id),
    onSuccess: result => {
      refresh();
      // 200 dönmesi "yayına aldım" demek değildir: ilan zaten yayında olabilir,
      // ya da sahibi askıda olduğu için hâlâ kimseye görünmüyor olabilir.
      if (!result.changed) toast.warning(t("listings.donePublishNoop"));
      else if (result.owner_suspended) toast.warning(t("listings.donePublishHidden"));
      else toast.success(t("listings.donePublish"));
    },
    onError: failed,
  });

  const editMutation = useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: AdminListingUpdate }) =>
      adminUpdateListing(id, patch),
    onSuccess: (row, { patch }) => {
      refresh();
      // Denetim yalnızca başlık/açıklama değiştiğinde yeniden çalışır; ilanın
      // eskiden beri taşıdığı işaret için "yeni metin işaretlendi" demeyelim.
      const touchedText = "title" in patch || "description" in patch;
      if (touchedText && row.is_flagged) toast.warning(t("listings.doneEditFlagged"));
      else toast.success(t("listings.doneEdit"));
      setEditing(null);
      setEditError(null);
    },
    onError: err => setEditError(failed(err)),
  });

  const actionMutation = useMutation({
    mutationFn: ({ a, note }: { a: DialogAction; note: string }) => {
      switch (a.kind) {
        case "unpublish":
          return reviewFlagged("listing", a.listing.id, "remove", note);
        case "restore":
          return restoreRemoved("listing", a.listing.id, note);
        case "delete":
          return adminDeleteListing(a.listing.id, note);
      }
    },
    onSuccess: (data, { a }) => {
      refresh();
      if (a.kind === "delete") {
        toast.success(t("listings.doneDelete"), { description: t("listings.doneDeleteDesc") });
        // Silinen kayıt açık bir pencerede duruyor olabilir; artık yok.
        if (selected?.id === a.listing.id) setSelected(null);
        if (editing?.id === a.listing.id) setEditing(null);
      } else if (a.kind === "unpublish") {
        toast.success(t("admin.doneRemoveListing"));
      } else {
        // Geri alma ilanı KALDIRILMADAN ÖNCEKİ hâline döndürür: sahibi onu
        // zaten kapatmışsa ilan yayına GİRMEZ, "yeniden yayında" demek yalan olur.
        const result = data as RestoreResult;
        if (result.is_active === false) toast.warning(t("admin.doneRestoreListingStillClosed"));
        else toast.success(t("admin.doneRestoreListing"));
      }
      setAction(null);
      setActionError(null);
    },
    onError: err => setActionError(failed(err)),
  });

  const busy = publishMutation.isPending || actionMutation.isPending;
  const filtering = query !== "" || status !== "all";

  // Bu sayfa yalnızca yöneticiye açıktır.
  if (!isAdmin) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center px-6 text-center gap-4 pb-24">
        <h1 className="text-2xl font-semibold text-foreground">{t("listings.closedTitle")}</h1>
        <p className="text-sm text-muted-foreground max-w-sm">{t("listings.closedDesc")}</p>
        <Button onClick={() => navigate("/swipe")} className="rounded-full px-6">
          {t("listings.goDiscover")}
        </Button>
        <BottomNav />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex flex-col pb-24">
      <AppHeader
        title={t("nav.houses")}
        rightAction={
          <button
            onClick={() => listQuery.refetch()}
            aria-label={t("admin.refresh")}
            title={t("admin.refresh")}
            className="w-10 h-10 rounded-2xl bg-card flex items-center justify-center text-foreground hover:bg-muted transition-colors"
            style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
          >
            <RefreshCw className="w-5 h-5" />
          </button>
        }
      />

      <div className="px-6 pt-4 pb-2">
        <h1 className="text-2xl font-bold text-foreground">{t("listings.heading")}</h1>
        <p className="text-sm text-muted-foreground mt-1">{t("listings.sub")}</p>
      </div>

      {/* Arama — başlık, ilçe ve ilan sahibinde sunucu tarafında çalışır. */}
      <div className="px-6 pt-2">
        <div className="relative">
          <Search className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
          <Input
            value={search}
            onChange={e => setSearch(e.target.value)}
            aria-label={t("listings.searchLabel")}
            placeholder={t("listings.searchPlaceholder")}
            className="rounded-2xl pl-9 pr-9"
          />
          {search && (
            <button
              type="button"
              onClick={() => setSearch("")}
              aria-label={t("listings.searchClear")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Durum süzgeci */}
      <div className="px-6 py-3">
        <div className="flex gap-2 overflow-x-auto scrollbar-hide">
          {STATUS_OPTIONS.map(option => (
            <button
              key={option.value}
              onClick={() => setStatus(option.value)}
              className={`px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-all ${
                status === option.value
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "bg-card border border-border text-foreground hover:border-primary/30"
              }`}
            >
              {t(option.key)}
            </button>
          ))}
        </div>
      </div>

      <div className="px-6 flex-1">
        {listQuery.isPending ? (
          <div className="text-center py-16 text-sm text-muted-foreground">{t("listings.loading")}</div>
        ) : listQuery.isError ? (
          <div className="text-center py-16 space-y-3">
            <p className="font-semibold text-foreground">{t("listings.loadFailed")}</p>
            <p className="text-sm text-muted-foreground">{t("listings.backendHint")}</p>
            <Button variant="outline" size="sm" onClick={() => listQuery.refetch()} className="rounded-full">
              <RefreshCw className="w-3.5 h-3.5 mr-2" /> {t("common.retry")}
            </Button>
          </div>
        ) : rows.length === 0 ? (
          <div className="text-center py-16 space-y-3">
            <div className="w-20 h-20 rounded-3xl bg-muted flex items-center justify-center mx-auto">
              <Home className="w-10 h-10 text-muted-foreground" />
            </div>
            {/* Süzgeç varken "hiç ilan yok" demek yanlış olur: sunucu yalnız o
                süzgece uyanları döndürüyor. Sayfa başında da aynı sorun var. */}
            <p className="font-semibold text-foreground">
              {t(filtering || page > 0 ? "listings.emptyFilteredTitle" : "listings.emptyTitle")}
            </p>
            <p className="text-sm text-muted-foreground">
              {t(filtering || page > 0 ? "listings.emptyFilteredDesc" : "listings.emptyDesc")}
            </p>
            {page > 0 && (
              <Button variant="outline" size="sm" onClick={() => setPage(0)} className="rounded-full">
                {t("listings.pageFirst")}
              </Button>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">{t("listings.resultCount", { count: n(rows.length) })}</p>
            {rows.map(listing => (
              <ListingRow
                key={listing.id}
                listing={listing}
                busy={busy}
                onDetails={() => setSelected(listing)}
                onEdit={() => {
                  setEditError(null);
                  setEditing(listing);
                }}
                onPublish={() => publishMutation.mutate(listing.id)}
                onAction={a => {
                  setActionError(null);
                  setAction(a);
                }}
              />
            ))}

            {/* Sayfalama: sunucu sayfa başına en çok PAGE_SIZE satır döndürür,
                toplam sayıyı vermez — "sonraki" ancak sayfa doluysa anlamlıdır. */}
            {(page > 0 || rows.length === PAGE_SIZE) && (
              <div className="flex items-center justify-between gap-3 py-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === 0}
                  onClick={() => setPage(p => Math.max(0, p - 1))}
                  className="rounded-full"
                >
                  <ChevronLeft className="w-3.5 h-3.5 mr-1" /> {t("listings.pagePrev")}
                </Button>
                <span className="text-xs text-muted-foreground tabular-nums">
                  {t("listings.pageLabel", { page: n(page + 1) })}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={rows.length < PAGE_SIZE}
                  onClick={() => setPage(p => p + 1)}
                  className="rounded-full"
                >
                  {t("listings.pageNext")} <ChevronRight className="w-3.5 h-3.5 ml-1" />
                </Button>
              </div>
            )}
          </div>
        )}
      </div>

      <ListingDetailModal listing={selected} onClose={() => setSelected(null)} />

      <EditDialog
        listing={editing}
        pending={editMutation.isPending}
        error={editError}
        onClose={() => {
          if (editMutation.isPending) return;
          setEditing(null);
          setEditError(null);
        }}
        onSave={patch => {
          if (editing) editMutation.mutate({ id: editing.id, patch });
        }}
      />

      <ConfirmDialog
        open={action !== null}
        // Kapanış animasyonu sırasında `action` null olur; son biçim korunsun.
        title={t(
          action?.kind === "delete"
            ? "listings.dlgDeleteTitle"
            : action?.kind === "restore"
              ? "admin.dlgRestoreListingTitle"
              : "admin.dlgRemoveListingTitle",
        )}
        desc={t(
          action?.kind === "delete"
            ? "listings.dlgDeleteDesc"
            : action?.kind === "restore"
              ? "admin.dlgRestoreListingDesc"
              : "admin.dlgRemoveListingDesc",
        )}
        warning={
          action?.kind === "delete"
            ? t("listings.dlgDeleteWarn")
            : // Kaldırılmadan önce kapalı olan ilan geri alınca yayına GİRMEZ;
              // yönetici bunu düğmeye basmadan önce bilmeli.
              action?.kind === "restore" && action.listing.active_before_removal === false
              ? t("admin.staysClosedWarn")
              : null
        }
        input={action?.kind === "delete" ? "reason" : "note"}
        inputLabel={t(action?.kind === "delete" ? "listings.dlgDeleteReasonLabel" : "admin.dlgNoteLabel")}
        inputPlaceholder={t(
          action?.kind === "delete" ? "listings.dlgDeleteReasonPlaceholder" : "admin.dlgNotePlaceholder",
        )}
        destructive={action?.kind !== "restore"}
        pending={actionMutation.isPending}
        error={actionError}
        onClose={() => {
          if (actionMutation.isPending) return;
          setAction(null);
          setActionError(null);
        }}
        onConfirm={note => {
          if (action) actionMutation.mutate({ a: action, note });
        }}
      />

      <BottomNav />
    </div>
  );
};

/* ─── Detail Modal ─── */
const ListingDetailModal = ({
  listing,
  onClose,
}: {
  listing: AdminListing | null;
  onClose: () => void;
}) => {
  const navigate = useNavigate();
  const { isLoggedIn, user: me } = useAuth();
  const { t, n } = useI18n();
  const [photoIndex, setPhotoIndex] = useState(0);

  if (!listing) return null;

  const isOwn = me !== null && listing.owner_id === me.id;

  // Girişliyse beğeni gönderir (eşleşme akışına girer); değilse girişe yönlendirir
  const handleContact = async () => {
    if (!isLoggedIn) {
      navigate("/login");
      return;
    }
    try {
      const res = await postSwipe(listing.id, "like");
      if (res.matched) {
        toast.success(t("swipe.matched"), { description: t("listings.matchedDesc") });
        navigate("/messages");
      } else {
        toast.success(t("listings.likeSent"), { description: t("listings.likeSentDesc") });
        onClose();
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("listings.likeFailed"));
    }
  };

  const house = isHouse(listing);
  const features = listingFeatures(listing);
  // Beğeni yalnızca gerçekten görünür olan ilanda çalışır; pasif ya da sahibi
  // askıda olan ilan için düğme göstermek yapılamayan bir şeyi vaat ederdi.
  const contactable = listing.is_active && !listing.owner_suspended;

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
            <button onClick={onClose} aria-label={t("common.close")} className="w-8 h-8 rounded-full bg-muted/80 backdrop-blur-sm flex items-center justify-center">
              <X className="w-4 h-4 text-foreground" />
            </button>
          </div>

          {/* Photo gallery */}
          {listing.photos.length > 0 && (
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
          )}

          {/* Info */}
          <div className="p-5 space-y-4">
            <div>
              <h2 className="text-xl font-bold text-foreground">{listing.title}</h2>
              <div className="flex items-center gap-3 mt-1 text-sm text-muted-foreground">
                <span className="flex items-center gap-1"><MapPin className="w-3.5 h-3.5" /> {listing.district}</span>
                {listing.room_count && (
                  <>
                    <span>·</span>
                    <span className="flex items-center gap-1"><BedDouble className="w-3.5 h-3.5" /> {listing.room_count}</span>
                  </>
                )}
                <span>·</span>
                <span className="font-bold text-accent text-base">
                  {priceLabel(listing, n)}{house ? t("common.perMonth") : ""}
                </span>
              </div>
            </div>

            {/* Adil fiyat analizi (ev arkadaşlığı bazlı oda payı) */}
            {house && <FairPriceBadge listingId={listing.id} detailed />}

            <hr className="border-border" />

            {/* Description */}
            <div>
              <h3 className="text-sm font-bold text-foreground mb-2">{t("listings.description")}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-line">{listing.description}</p>
            </div>

            {!house && (
              <div className="flex items-center gap-2">
                <DollarSign className="w-3.5 h-3.5 text-accent" />
                <span className="text-xs font-semibold text-foreground">
                  {t("listings.budget")}: {priceLabel(listing, n)}
                </span>
              </div>
            )}

            {/* Ev özellikleri — yalnızca ilan sahibinin işaretledikleri */}
            {house && features.length > 0 && (
              <>
                <hr className="border-border" />
                <div>
                  <h4 className="text-xs font-semibold text-foreground mb-2">{t("listings.features")}</h4>
                  <div className="flex flex-wrap gap-2">
                    {features.map(key => (
                      <span key={key} className="px-3 py-1 rounded-full text-[11px] font-medium bg-lavender/50 text-foreground">
                        {t(featureLabels[key])}
                      </span>
                    ))}
                  </div>
                </div>
              </>
            )}

            {/* Kurallar (ev ilanı) */}
            {house && (
              <>
                <hr className="border-border" />
                <div>
                  <h4 className="text-xs font-semibold text-foreground mb-2">{t("listings.rules")}</h4>
                  <div className="flex flex-wrap gap-2">
                    <span className={`px-3 py-1 rounded-full text-[11px] font-medium ${listing.smoking_allowed ? "bg-accent/15 text-foreground" : "bg-muted text-muted-foreground"}`}>
                      {listing.smoking_allowed ? t("listings.smokingAllowed") : t("listings.smokingBanned")}
                    </span>
                    <span className={`px-3 py-1 rounded-full text-[11px] font-medium ${listing.pets_allowed ? "bg-accent/15 text-foreground" : "bg-muted text-muted-foreground"}`}>
                      {listing.pets_allowed ? t("listings.petsAllowed") : t("listings.petsBanned")}
                    </span>
                  </div>
                </div>
              </>
            )}

            {/* CTA */}
            {!isOwn && contactable && (
              <Button
                onClick={handleContact}
                className="w-full h-12 rounded-full bg-gradient-to-r from-primary to-secondary text-primary-foreground font-bold text-sm"
              >
                <MessageCircle className="w-4 h-4 mr-2" /> {isLoggedIn ? t("listings.contact") : t("listings.contactLogin")}
              </Button>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

export default Listings;
