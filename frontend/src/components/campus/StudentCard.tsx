import { motion, useReducedMotion } from "framer-motion";
import { BRAND } from "@/lib/brand";
import { cn, initials } from "@/lib/utils";
import { useI18n } from "@/i18n";

interface StudentCardProps {
  name: string;
  photo?: string | null;
  university?: string | null;
  department?: string | null;
  year?: number | null;
  /** Hesap numarası; kartta "Üye no" olarak basılır, barkod da ondan üretilir. */
  memberNo?: number | null;
  /**
   * Mühür yalnızca gerçekten doğrulanmış bir şey varken basılır. Üniversite
   * adı e-posta alan adından otomatik atanır ve kullanıcı değiştiremez
   * (backend/app/universities.py); yani üniversitesi olan hesap bir .edu.tr
   * adresiyle açılmıştır.
   */
  verified?: boolean;
  /** Ana sayfadaki boş kart: alanlar yer tutucu, mühür sayfa açılınca basılır. */
  blank?: boolean;
  /** Mührü bir kez, sayfa açılışında basar. */
  animateStamp?: boolean;
  className?: string;
  children?: React.ReactNode;
}

/**
 * Barkod: üye numarasından türetilen çizgiler. Okunabilir bir kod değil;
 * aynı kişi her yerde aynı barkodu taşısın diye numaradan üretilir.
 */
const Barcode = ({ seed }: { seed: string }) => {
  const bars: { x: number; w: number }[] = [];
  let x = 0;
  for (const ch of `*${seed}*`) {
    const c = ch.charCodeAt(0);
    for (let k = 0; k < 5; k++) {
      const w = ((c >> k) & 1) + 1 + (k % 2);
      if (k % 2 === 0) bars.push({ x, w });
      x += w + 1;
    }
  }
  return (
    <svg viewBox={`0 0 ${x} 20`} preserveAspectRatio="none" className="h-5 w-28 text-foreground/80" aria-hidden="true">
      {bars.map((b, i) => (
        <rect key={i} x={b.x} y={0} width={b.w} height={20} fill="currentColor" />
      ))}
    </svg>
  );
};

/**
 * Öğrenci kimliği gibi basılmış profil kartı. Sitenin akılda kalan tek
 * parçası: bir kişiyi temsil eden her yerde (profil, beğeniler, eşleşme)
 * aynı kart görünür.
 */
const StudentCard = ({
  name, photo, university, department, year, memberNo, verified = false,
  blank = false, animateStamp = false, className, children,
}: StudentCardProps) => {
  const { t } = useI18n();
  const reduce = useReducedMotion();
  const no = memberNo != null ? String(memberNo).padStart(5, "0") : null;

  const stamp = (
    <span className="stamp text-[10px] px-2 py-1">
      <span className="text-[13px]">{t("card.stampTop")}</span>
      <span className="font-semibold normal-case tracking-normal">{t("card.stampBottom")}</span>
    </span>
  );

  return (
    <div
      className={cn(
        "relative bg-card text-card-foreground rounded-xl border border-border overflow-hidden",
        className,
      )}
    >
      {/* Üst bant: kurumun adı, kartın sahibi değil */}
      <div className="flex items-center justify-between gap-3 bg-primary text-primary-foreground px-4 py-2">
        <span className="text-[12px] font-semibold truncate">
          {blank ? t("card.blankUniversity") : university || t("card.noUniversity")}
        </span>
        <span className="font-display text-[13px] font-semibold opacity-80 shrink-0">{BRAND}</span>
      </div>

      <div className="flex gap-4 p-4 pb-3">
        <div className="w-[84px] shrink-0 aspect-[3/4] rounded-md overflow-hidden bg-muted border border-border flex items-center justify-center">
          {photo ? (
            <img src={photo} alt="" className="w-full h-full object-cover object-top" />
          ) : (
            <span className={cn("font-display text-3xl font-semibold", blank ? "text-muted-foreground/50" : "text-foreground/70")}>
              {blank ? "?" : initials(name)}
            </span>
          )}
        </div>

        <dl className="min-w-0 flex-1 space-y-1.5">
          <div>
            <dt className="sr-only">{t("card.name")}</dt>
            <dd className={cn("font-display text-2xl font-semibold leading-tight truncate", blank && "text-muted-foreground/60")}>
              {blank ? t("card.blankName") : name}
            </dd>
          </div>
          <div className="text-[13px] leading-snug">
            <dt className="sr-only">{t("card.department")}</dt>
            <dd className={cn("truncate", blank ? "text-muted-foreground/60" : "text-foreground")}>
              {blank ? t("card.blankDepartment") : department || "—"}
            </dd>
            {(year || blank) && (
              <dd className={blank ? "text-muted-foreground/60" : "text-muted-foreground"}>
                {blank ? t("card.blankYear") : t("likes.year", { year: year ?? 0 })}
              </dd>
            )}
          </div>
          {no && (
            <div className="flex items-baseline gap-1.5 text-[12px] text-muted-foreground">
              <dt>{t("card.memberNo")}</dt>
              <dd className="tabular-nums font-semibold text-foreground">{no}</dd>
            </div>
          )}
        </dl>
      </div>

      <div className="flex items-end justify-between px-4 pb-3 min-h-[36px]">
        <Barcode seed={no ?? (blank ? "00000" : name)} />
      </div>

      {children}

      {verified && (
        <div className="absolute right-4 bottom-3 -rotate-[9deg] pointer-events-none">
          {animateStamp && !reduce ? (
            <motion.div
              initial={{ scale: 1.9, opacity: 0, rotate: -4 }}
              animate={{ scale: 1, opacity: 1, rotate: 0 }}
              transition={{ delay: 0.55, duration: 0.28, ease: [0.2, 0.9, 0.3, 1.2] }}
            >
              {stamp}
            </motion.div>
          ) : (
            stamp
          )}
        </div>
      )}
    </div>
  );
};

export default StudentCard;
