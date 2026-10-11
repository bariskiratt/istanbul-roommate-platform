import { Heart } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n";
import type { Prompt, TimelineItem } from "@/lib/prompts";

/**
 * Hinge'in profil düzeni: fotoğraflar ve aralarında soru-cevap kartları.
 * Destede (ilan sahibi), Beğeniler'de (beğenen kişi) ve kendi profil
 * önizlemende aynı parçalar kullanılır; kartların metni lib/prompts.ts'te
 * üretilir.
 *
 * Kart bilerek kâğıt dokusu taşımaz: çizgili kâğıt kişinin KENDİ yazdığı
 * metindir (bio, ilan yazısı), oysa kart cevapları seçimlerinden üretilir.
 * Sade kart, büyük serif cevap: Hinge'in kendisi.
 */

/** Fotoğrafın ya da kartın köşesindeki beğeni düğmesi. */
export const LikeHeart = ({
  onClick,
  className,
}: {
  onClick: () => void;
  className?: string;
}) => {
  const { t } = useI18n();
  return (
    <button
      type="button"
      onClick={e => {
        // Kartın kendi tıklama/sürükleme davranışına karışmasın.
        e.stopPropagation();
        onClick();
      }}
      aria-label={t("like.item")}
      title={t("like.item")}
      className={cn(
        "w-11 h-11 rounded-full bg-card text-foreground border border-border flex items-center justify-center transition-transform duration-150 active:scale-95 hover:border-foreground/50",
        className,
      )}
    >
      <Heart className="w-5 h-5" strokeWidth={2.2} />
    </button>
  );
};

export const PromptCard = ({
  prompt,
  onLike,
  className,
}: {
  prompt: Pick<Prompt, "question" | "answer" | "marker">;
  onLike?: () => void;
  className?: string;
}) => (
  <div className={cn("relative rounded-xl border border-border bg-card px-5 pt-4 pb-5", className)}>
    <p className="text-[13px] font-semibold text-muted-foreground">{prompt.question}</p>
    <p className={cn("mt-1.5 font-display text-[1.55rem] leading-[1.18] text-foreground", onLike && "pr-12")}>
      {prompt.marker ? <span className="marker">{prompt.answer}</span> : prompt.answer}
    </p>
    {onLike && <LikeHeart onClick={onLike} className="absolute bottom-3 right-3" />}
  </div>
);

export const TimelinePhoto = ({
  url,
  onLike,
  className,
}: {
  url: string;
  onLike?: () => void;
  className?: string;
}) => (
  <div className={cn("relative rounded-xl overflow-hidden bg-muted aspect-[4/5]", className)}>
    <img src={url} alt="" loading="lazy" draggable={false} className="w-full h-full object-cover" />
    {onLike && <LikeHeart onClick={onLike} className="absolute bottom-3 right-3" />}
  </div>
);

/** Kart, fotoğraf, kart, fotoğraf… `onLike` verilirse her birinde kalp çıkar. */
const ProfileTimeline = ({
  items,
  onLike,
  className,
}: {
  items: TimelineItem[];
  onLike?: (item: TimelineItem) => void;
  className?: string;
}) => {
  if (items.length === 0) return null;
  return (
    <div className={cn("space-y-3", className)}>
      {items.map(item =>
        item.kind === "photo" ? (
          <TimelinePhoto
            key={`photo-${item.index}`}
            url={item.url}
            onLike={onLike && (() => onLike(item))}
          />
        ) : (
          <PromptCard
            key={`prompt-${item.prompt.key}`}
            prompt={item.prompt}
            onLike={onLike && (() => onLike(item))}
          />
        ),
      )}
    </div>
  );
};

export default ProfileTimeline;
