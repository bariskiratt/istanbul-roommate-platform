import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/contexts/AuthContext";
import { fetchListings, type ReceivedLike } from "@/lib/api";
import { describeLikedPrompt } from "@/lib/prompts";
import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n";
import type { TranslationKey } from "@/i18n/translations";

type LikeInfo = Pick<ReceivedLike, "target" | "comment" | "listing_id" | "listing_title">;

const labelKey = (like: LikeInfo): TranslationKey => {
  if (like.target?.kind === "photo") return "likes.target.photo";
  if (like.target?.kind === "prompt") {
    return like.target.prompt_key === "description" ? "likes.target.description" : "likes.target.prompt";
  }
  return "likes.target.listing";
};

/**
 * Gelen beğeninin bağlamı: NEYİ beğendi (fotoğrafın, cevabın, ilan yazın ya
 * da ilanın tamamı) ve yorumu. Hinge'de olduğu gibi kişinin profilinden önce
 * gelir; yorum, kişinin kendi yazdığı metin olduğu için çizgili kâğıtta.
 *
 * Beğenilen kartın metni beğeniyi ALANIN kendi verisinden bugünkü hâliyle
 * üretilir (lib/prompts.ts describeLikedPrompt); ilan listesi Profil ile aynı
 * önbellek anahtarını kullanır.
 */
const LikeContext = ({ like, compact = false }: { like: LikeInfo; compact?: boolean }) => {
  const { t, n, locale } = useI18n();
  const { isLoggedIn, user: me } = useAuth();

  const needsListing = like.target?.kind === "prompt" && !compact;
  const { data: myListings } = useQuery({
    queryKey: ["listings", "mine"],
    queryFn: () => fetchListings({ mine: true }),
    enabled: isLoggedIn && me !== null && needsListing,
  });

  const prompt =
    like.target?.kind === "prompt" && like.target.prompt_key && me && !compact
      ? describeLikedPrompt(
          like.target.prompt_key,
          me,
          myListings?.find(l => l.id === like.listing_id),
          { t, n, locale },
        )
      : null;

  if (compact) {
    return (
      <div className="mt-1.5 space-y-0.5">
        <p className="text-[12px] font-semibold text-foreground">{t(labelKey(like))}</p>
        {like.comment && (
          <p className="text-[13px] text-foreground line-clamp-2 break-words">
            <span className="sr-only">{t("likes.comment")}: </span>“{like.comment}”
          </p>
        )}
      </div>
    );
  }

  return (
    <section className="space-y-2.5">
      <div className="flex items-start gap-3">
        {like.target?.kind === "photo" && like.target.photo_url && (
          <div className="w-16 shrink-0 aspect-[4/5] rounded-lg overflow-hidden bg-muted border border-border">
            <img
              src={like.target.photo_url}
              alt=""
              className="w-full h-full object-cover"
              // Sahibi fotoğrafı ilandan kaldırdıysa dosya silinmiş olabilir.
              onError={e => (e.currentTarget.parentElement!.style.display = "none")}
            />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <p className="text-[15px] font-semibold text-foreground">{t(labelKey(like))}</p>
          {prompt && (
            <div className="mt-1">
              <p className="text-[12px] text-muted-foreground">{prompt.question}</p>
              {prompt.answer && (
                <p className={cn("font-display text-lg leading-snug text-foreground", like.target?.prompt_key === "description" && "line-clamp-2 text-base")}>
                  {prompt.answer}
                </p>
              )}
            </div>
          )}
          <p className="mt-1 text-[12px] text-muted-foreground truncate">
            {t("likes.onListing", { title: like.listing_title })}
          </p>
        </div>
      </div>
      {like.comment && (
        <p className="paper-ruled rounded-lg text-[15px] text-foreground whitespace-pre-line break-words">
          <span className="sr-only">{t("likes.comment")}: </span>
          {like.comment}
        </p>
      )}
    </section>
  );
};

export default LikeContext;
