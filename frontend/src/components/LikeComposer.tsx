import { useEffect, useId, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { PromptCard } from "@/components/campus/ProfileTimeline";
import { useDialogFocus } from "@/hooks/use-dialog-focus";
import { LIKE_COMMENT_MAX } from "@/lib/api";
import { useI18n } from "@/i18n";

/** Neyin beğenildiği: panelin üstünde küçük bir önizleme olarak durur. */
export type LikePreview =
  | { kind: "photo"; url: string }
  | { kind: "prompt"; question: string; answer: string; marker?: boolean }
  /** İlan sahibinin kendi yazdığı açıklama: çizgili kâğıtta. */
  | { kind: "text"; question: string; text: string };

interface LikeComposerProps {
  open: boolean;
  onClose: () => void;
  /** Beğeniyi alacak kişinin adı (başlık altındaki cümle için). */
  recipient: string;
  preview: LikePreview | null;
  /**
   * Beğeniyi gönderir. Hata fırlatırsa panel AÇIK kalır ve yorum yerinde
   * durur: denetime takılan yorum (422) silinip yeniden yazdırılmamalı.
   */
  onSend: (comment: string) => Promise<void>;
}

/**
 * Hinge'deki "yorum ekle" paneli: beğenilen fotoğraf ya da kart üstte, altında
 * isteğe bağlı yorum. Kaydırma kartının DIŞINDA kurulur (bkz. SwipeScreen):
 * sürüklenen kart `transform` taşıdığı için içindeki `position: fixed` panel
 * ekranı kaplayamazdı.
 */
const LikeComposer = ({ open, onClose, recipient, preview, onSend }: LikeComposerProps) => {
  const { t } = useI18n();
  const [comment, setComment] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const headingId = useId();
  const commentId = useId();

  useEffect(() => {
    if (!open) return;
    setComment("");
    setError(null);
    setSending(false);
  }, [open]);

  useDialogFocus(open, onClose, panelRef, inputRef);

  const submit = async () => {
    if (sending) return;
    setSending(true);
    setError(null);
    try {
      await onSend(comment);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("like.failed"));
    } finally {
      setSending(false);
    }
  };

  return (
    <AnimatePresence>
      {open && preview && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center sm:p-4 bg-black/40 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={headingId}
            initial={{ y: 32, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 32, opacity: 0 }}
            transition={{ type: "spring", damping: 28, stiffness: 320 }}
            className="bg-card border border-border w-full sm:max-w-[440px] max-h-[92vh] rounded-t-2xl sm:rounded-2xl flex flex-col"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-start gap-3 px-5 pt-4 pb-3">
              <div className="flex-1 min-w-0">
                <h2 id={headingId} className="font-display text-2xl leading-tight text-foreground">
                  {t("like.title")}
                </h2>
                <p className="mt-1 text-[13px] text-muted-foreground leading-snug">
                  {t("like.sub", { name: recipient })}
                </p>
              </div>
              <button
                onClick={onClose}
                aria-label={t("common.close")}
                className="w-9 h-9 -mr-1.5 rounded-full flex items-center justify-center text-foreground hover:bg-muted transition-colors shrink-0"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-5 pb-2 space-y-4">
              {preview.kind === "photo" ? (
                <div className="w-36 aspect-[4/5] rounded-xl overflow-hidden bg-muted border border-border">
                  <img src={preview.url} alt={t("like.photo")} className="w-full h-full object-cover" />
                </div>
              ) : preview.kind === "prompt" ? (
                <PromptCard prompt={preview} />
              ) : (
                <div>
                  <p className="text-[13px] font-semibold text-muted-foreground mb-1.5">{preview.question}</p>
                  <p className="paper-ruled rounded-lg text-[14px] text-foreground line-clamp-4">{preview.text}</p>
                </div>
              )}

              <div>
                <div className="flex items-baseline justify-between mb-2">
                  <label htmlFor={commentId} className="text-[15px] font-semibold text-foreground">
                    {t("like.commentLabel")}{" "}
                    <span className="text-[13px] font-normal text-muted-foreground">{t("like.commentOptional")}</span>
                  </label>
                  <span className="text-[11px] text-muted-foreground tabular-nums">
                    {t("like.commentCounter", { count: comment.length, max: LIKE_COMMENT_MAX })}
                  </span>
                </div>
                <Textarea
                  id={commentId}
                  ref={inputRef}
                  value={comment}
                  // Sunucu sınırın üstünü 422 ile reddeder; girişte kırpıyoruz.
                  onChange={e => setComment(e.target.value.slice(0, LIKE_COMMENT_MAX))}
                  maxLength={LIKE_COMMENT_MAX}
                  placeholder={t("like.commentPlaceholder")}
                  aria-invalid={error ? true : undefined}
                  className="min-h-[88px] resize-none text-[15px]"
                />
              </div>

              {error && (
                <div role="alert" className="rounded-xl border border-destructive/40 bg-destructive/5 px-4 py-3">
                  <p className="text-[13px] text-destructive">{error}</p>
                </div>
              )}
            </div>

            <div className="px-5 pt-3 pb-[max(1rem,env(safe-area-inset-bottom))]">
              <Button onClick={submit} disabled={sending} className="w-full h-12 text-base">
                {sending ? t("like.sending") : t("like.send")}
              </Button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default LikeComposer;
