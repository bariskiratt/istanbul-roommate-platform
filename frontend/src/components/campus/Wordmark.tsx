import { BRAND } from "@/lib/brand";
import { cn } from "@/lib/utils";

const SIZES = {
  sm: "text-lg",
  md: "text-[1.4rem]",
  lg: "text-3xl",
} as const;

/**
 * Yazı logo: "evdes" fosforlu kalemle işaretlenmiş, ".tr" düz.
 *
 * Ad BRAND'den bölünerek basılır; adı elle iki yerde yazmak, biri
 * değişince logonun sessizce eskimesi demekti (bkz. lib/brand.ts).
 * İşaretleme, sitenin "en önemli şeyi fosforlu kalemle çiz" kuralının
 * markadaki karşılığı: öğrencinin defterinde altı çizilen kelime.
 */
const Wordmark = ({ size = "md", className }: { size?: keyof typeof SIZES; className?: string }) => {
  const dot = BRAND.indexOf(".");
  const head = dot > 0 ? BRAND.slice(0, dot) : BRAND;
  const tail = dot > 0 ? BRAND.slice(dot) : "";
  return (
    <span
      className={cn("font-display font-semibold tracking-[-0.02em] leading-none text-foreground whitespace-nowrap", SIZES[size], className)}
      aria-label={BRAND}
    >
      <span className="marker" aria-hidden="true">{head}</span>
      <span aria-hidden="true">{tail}</span>
    </span>
  );
};

export default Wordmark;
