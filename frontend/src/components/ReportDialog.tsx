import { useEffect, useId, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { Flag, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Textarea } from "@/components/ui/textarea";
import {
  ApiError,
  fetchReportReasons,
  postReport,
  type ReportTargetType,
} from "@/lib/api";
import { reportReasonKey } from "@/lib/reportReasons";
import { useI18n } from "@/i18n";
import type { TranslationKey } from "@/i18n/translations";

/** Sunucu `note` alanını en fazla 500 karakter kabul eder. */
const NOTE_MAX = 500;

const titleKeys: Record<ReportTargetType, TranslationKey> = {
  listing: "report.titleListing",
  user: "report.titleUser",
  message: "report.titleMessage",
};

interface ReportDialogProps {
  open: boolean;
  onClose: () => void;
  targetType: ReportTargetType;
  targetId: number;
  /** Başlık altında gösterilen ilan başlığı / kullanıcı adı (varsa). */
  targetLabel?: string;
}

const ReportDialog = ({ open, onClose, targetType, targetId, targetLabel }: ReportDialogProps) => {
  const { t } = useI18n();
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  // Kapanışta odağı çağıran düğmeye geri veririz (klavye kullanıcısı
  // listenin/başlığın başına fırlamasın).
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const headingId = useId();

  const { data: reasons, isPending, isError } = useQuery({
    queryKey: ["report-reasons"],
    queryFn: fetchReportReasons,
    enabled: open,
    staleTime: Infinity,
  });

  // Her açılışta temiz başla.
  useEffect(() => {
    if (!open) return;
    setReason("");
    setNote("");
    setError(null);
    returnFocusRef.current = document.activeElement as HTMLElement | null;
    // Panel çizildikten sonra odağı kapat düğmesine al.
    const id = window.setTimeout(() => closeRef.current?.focus(), 0);
    return () => {
      window.clearTimeout(id);
      returnFocusRef.current?.focus?.();
    };
  }, [open]);

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

  const submit = async () => {
    if (!reason || sending) return;
    setSending(true);
    setError(null);
    try {
      await postReport(targetType, targetId, reason, note);
      toast.success(t("report.successTitle"), { description: t("report.successDesc") });
      onClose();
    } catch (err) {
      // Sunucu mesajı (409 "zaten raporladın", 404 "içerik bulunamadı" …)
      // olduğu gibi gösterilir; genel hata metniyle örtülmez.
      const message =
        err instanceof ApiError || err instanceof Error ? err.message : t("common.error");
      setError(message);
      toast.error(t("report.failedTitle"), { description: message });
    } finally {
      setSending(false);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={headingId}
            initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.95, opacity: 0 }}
            className="bg-card rounded-2xl border border-border shadow-2xl w-full max-w-[440px] max-h-[85vh] flex flex-col"
            onClick={e => e.stopPropagation()}
          >
            {/* Başlık */}
            <div className="flex items-start gap-3 px-6 py-4 border-b border-border">
              <Flag className="w-5 h-5 mt-1 text-destructive shrink-0" />
              <div className="flex-1 min-w-0">
                <h2 id={headingId} className="font-display text-xl font-semibold leading-tight text-foreground">
                  {t(titleKeys[targetType])}
                </h2>
                {targetLabel && (
                  <p className="text-[13px] text-muted-foreground truncate">{targetLabel}</p>
                )}
              </div>
              <button
                ref={closeRef}
                onClick={onClose}
                aria-label={t("common.close")}
                className="w-9 h-9 -mr-2 rounded-full flex items-center justify-center text-foreground hover:bg-muted transition-colors shrink-0"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* İçerik */}
            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
              <p className="text-[14px] text-muted-foreground leading-relaxed">{t("report.sub")}</p>

              <div>
                <h3 className="text-[15px] font-semibold text-foreground mb-3">{t("report.reasonLabel")}</h3>
                {isPending ? (
                  <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
                ) : isError || !reasons ? (
                  <p className="text-sm text-destructive">{t("report.reasonsFailed")}</p>
                ) : (
                  <RadioGroup value={reason} onValueChange={setReason} className="gap-2">
                    {reasons.map(value => {
                      const labelKey = reportReasonKey(value);
                      const active = reason === value;
                      return (
                        <label
                          key={value}
                          className={`flex items-center gap-3 px-4 py-3 rounded-xl border cursor-pointer transition-colors ${
                            active ? "border-foreground bg-muted" : "border-input hover:border-foreground/40"
                          }`}
                        >
                          <RadioGroupItem value={value} />
                          <span className="text-[14px] font-semibold text-foreground">
                            {labelKey ? t(labelKey) : value}
                          </span>
                        </label>
                      );
                    })}
                  </RadioGroup>
                )}
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-[15px] font-semibold text-foreground">{t("report.noteLabel")}</h3>
                  <span className="text-[11px] text-muted-foreground tabular-nums">
                    {t("report.noteCounter", { count: note.length, max: NOTE_MAX })}
                  </span>
                </div>
                <Textarea
                  value={note}
                  // Sunucu 500'ün üstünü 422 ile reddeder; girişte kırpıyoruz.
                  onChange={e => setNote(e.target.value.slice(0, NOTE_MAX))}
                  maxLength={NOTE_MAX}
                  placeholder={t("report.notePlaceholder")}
                  className="min-h-[96px] resize-none"
                />
              </div>

              {error && (
                <div className="rounded-xl border border-destructive/40 bg-destructive/5 px-4 py-3">
                  <p className="text-[13px] text-destructive">{error}</p>
                </div>
              )}
            </div>

            {/* Alt çubuk */}
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-border">
              <Button variant="ghost" onClick={onClose} className="rounded-full h-11 px-5 text-sm">
                {t("common.cancel")}
              </Button>
              <Button
                onClick={submit}
                disabled={!reason || sending}
                className="rounded-full h-11 px-6 text-sm font-semibold bg-destructive text-destructive-foreground hover:bg-destructive/90"
              >
                {sending ? t("report.submitting") : t("report.submit")}
              </Button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default ReportDialog;
