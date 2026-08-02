import { useEffect, useId, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ShieldAlert, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useI18n } from "@/i18n";
import type { TranslationKey } from "@/i18n/translations";

/** Sunucu not/sebep alanlarını en fazla 500 karakter kabul eder. */
const NOTE_MAX = 500;

/** Panelden tetiklenebilen yönetici eylemleri. */
export type AdminActionKind =
  | "resolve"
  | "reopen"
  | "removeListing"
  | "removeMessage"
  | "restoreListing"
  | "restoreMessage"
  | "clear"
  | "suspend"
  | "unsuspend"
  | "deleteUser";

interface ActionConfig {
  titleKey: TranslationKey;
  descKey: TranslationKey;
  /** "none": metin alanı yok, "note": isteğe bağlı not, "reason": zorunlu sebep. */
  input: "none" | "note" | "reason";
  /** Yıkıcı eylemler onay düğmesini kırmızı gösterir. */
  destructive: boolean;
  /**
   * Zorunlu sebep alanının başlığı/ipucu. Verilmezse askıya almanın metni
   * kullanılır — sebep isteyen tek eylem uzun süre o olduğu için metin
   * sabitti; hesap silmede "Askı sebebi" yazmak yanlış olurdu.
   */
  reasonLabelKey?: TranslationKey;
  reasonPlaceholderKey?: TranslationKey;
}

const configs: Record<AdminActionKind, ActionConfig> = {
  resolve: { titleKey: "admin.dlgResolveTitle", descKey: "admin.dlgResolveDesc", input: "note", destructive: false },
  reopen: { titleKey: "admin.dlgReopenTitle", descKey: "admin.dlgReopenDesc", input: "none", destructive: false },
  removeListing: {
    titleKey: "admin.dlgRemoveListingTitle",
    descKey: "admin.dlgRemoveListingDesc",
    input: "note",
    destructive: true,
  },
  removeMessage: {
    titleKey: "admin.dlgRemoveMessageTitle",
    descKey: "admin.dlgRemoveMessageDesc",
    input: "note",
    destructive: true,
  },
  restoreListing: {
    titleKey: "admin.dlgRestoreListingTitle",
    descKey: "admin.dlgRestoreListingDesc",
    input: "note",
    destructive: false,
  },
  restoreMessage: {
    titleKey: "admin.dlgRestoreMessageTitle",
    descKey: "admin.dlgRestoreMessageDesc",
    input: "note",
    destructive: false,
  },
  clear: { titleKey: "admin.dlgClearTitle", descKey: "admin.dlgClearDesc", input: "note", destructive: false },
  suspend: { titleKey: "admin.dlgSuspendTitle", descKey: "admin.dlgSuspendDesc", input: "reason", destructive: true },
  unsuspend: {
    titleKey: "admin.dlgUnsuspendTitle",
    descKey: "admin.dlgUnsuspendDesc",
    input: "none",
    destructive: false,
  },
  // Sebep ZORUNLU: silinen satır geri gelmiyor ve denetim kaydına yazılacak
  // tek açıklama bu. Sunucu da boş gerekçeyi 422 ile reddediyor.
  deleteUser: {
    titleKey: "admin.dlgDeleteUserTitle",
    descKey: "admin.dlgDeleteUserDesc",
    input: "reason",
    destructive: true,
    reasonLabelKey: "admin.dlgDeleteUserReasonLabel",
    reasonPlaceholderKey: "admin.dlgDeleteUserReasonPlaceholder",
  },
};

interface AdminActionDialogProps {
  open: boolean;
  kind: AdminActionKind;
  /** Başlık altında gösterilen ilan başlığı / kullanıcı adı / mesaj özeti. */
  targetLabel?: string;
  /**
   * Bu somut hedefe özel uyarı (sabit açıklamanın söyleyemeyeceği şey).
   * Örnek: geri alınacak ilan kaldırılmadan önce de kapalıydı, yani geri
   * alma onu yayına sokmayacak.
   */
  warning?: string | null;
  /** İstek sürüyor mu (çağıran mutation'dan gelir). */
  pending?: boolean;
  /** Sunucudan dönen hata metni; panelde olduğu gibi gösterilir. */
  error?: string | null;
  onClose: () => void;
  /** Onaylandığında not/sebep metniyle çağrılır (boş olabilir). */
  onConfirm: (note: string) => void;
}

/**
 * Yönetici eylemleri için ortak onay penceresi. Yıkıcı eylemler buradan
 * geçer; "resolve" ve "suspend" gibi eylemlerde karar notu da burada alınır.
 * Görünüm ReportDialog ile aynı desende (elle kurulmuş panel + odak tuzağı).
 */
const AdminActionDialog = ({
  open,
  kind,
  targetLabel,
  warning = null,
  pending = false,
  error = null,
  onClose,
  onConfirm,
}: AdminActionDialogProps) => {
  const { t } = useI18n();
  const [note, setNote] = useState("");
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  // Kapanışta odak, eylemi başlatan düğmeye geri döner.
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const headingId = useId();

  const config = configs[kind];

  // Her açılışta temiz başla.
  useEffect(() => {
    if (!open) return;
    setNote("");
    returnFocusRef.current = document.activeElement as HTMLElement | null;
    const id = window.setTimeout(() => closeRef.current?.focus(), 0);
    return () => {
      window.clearTimeout(id);
      returnFocusRef.current?.focus?.();
    };
  }, [open, kind]);

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

  // Sebep zorunlu olan eylemde (askıya alma) boş metinle onay verilemez.
  const blocked = pending || (config.input === "reason" && note.trim().length === 0);

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
            {/* Başlık */}
            <div className="flex items-start gap-3 px-6 py-4 border-b border-border">
              <div
                className={`w-9 h-9 rounded-2xl flex items-center justify-center shrink-0 ${
                  config.destructive ? "bg-destructive/10" : "bg-primary/10"
                }`}
              >
                <ShieldAlert
                  className={`w-4 h-4 ${config.destructive ? "text-destructive" : "text-primary"}`}
                />
              </div>
              <div className="flex-1 min-w-0">
                <h2 id={headingId} className="text-base font-bold text-foreground">
                  {t(config.titleKey)}
                </h2>
                {targetLabel && (
                  <p className="text-xs text-muted-foreground truncate">{targetLabel}</p>
                )}
              </div>
              <button
                ref={closeRef}
                onClick={onClose}
                aria-label={t("common.close")}
                className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-foreground hover:bg-muted/80 shrink-0"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* İçerik */}
            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
              <p className="text-sm text-muted-foreground">{t(config.descKey)}</p>

              {warning && (
                <div className="rounded-2xl border border-destructive/30 bg-destructive/5 px-4 py-3">
                  <p className="text-xs text-destructive">{warning}</p>
                </div>
              )}

              {config.input !== "none" && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-bold text-foreground">
                      {t(
                        config.input === "reason"
                          ? (config.reasonLabelKey ?? "admin.dlgReasonLabel")
                          : "admin.dlgNoteLabel",
                      )}
                    </h3>
                    <span className="text-[11px] text-muted-foreground tabular-nums">
                      {t("report.noteCounter", { count: note.length, max: NOTE_MAX })}
                    </span>
                  </div>
                  <Textarea
                    value={note}
                    // Sunucu 500'ün üstünü 422 ile reddeder; girişte kırpıyoruz.
                    onChange={e => setNote(e.target.value.slice(0, NOTE_MAX))}
                    maxLength={NOTE_MAX}
                    placeholder={t(
                      config.input === "reason"
                        ? (config.reasonPlaceholderKey ?? "admin.dlgReasonPlaceholder")
                        : "admin.dlgNotePlaceholder",
                    )}
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

            {/* Alt çubuk */}
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
                  config.destructive
                    ? "bg-destructive text-destructive-foreground hover:bg-destructive/90"
                    : ""
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

export default AdminActionDialog;
