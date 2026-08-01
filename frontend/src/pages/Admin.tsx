import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Flag, RefreshCw, ShieldCheck, UserX } from "lucide-react";
import { toast } from "sonner";
import AppHeader from "@/components/layout/AppHeader";
import BottomNav from "@/components/layout/BottomNav";
import AdminActionDialog, { type AdminActionKind } from "@/components/AdminActionDialog";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/i18n";
import type { TranslationKey } from "@/i18n/translations";
import { parseUtc } from "@/lib/date";
import { reportReasonKey } from "@/lib/reportReasons";
import {
  REMOVED_CONTENT,
  UNREADABLE_CONTENT,
  fetchAdminReports,
  fetchAdminSummary,
  fetchAdminUsers,
  fetchFlagged,
  resolveAdminReport,
  restoreRemoved,
  reviewFlagged,
  suspendUser,
  unsuspendUser,
  type AdminReport,
  type AdminReportStatus,
  type AdminUserRow,
  type FlaggedItem,
  type FlaggedKind,
  type FlaggedStatus,
  type RestoreResult,
} from "@/lib/api";

/** useI18n().t ile aynı imza; alt bileşenlere aktarmak yerine kendileri çağırır. */
type Translate = (key: TranslationKey, vars?: Record<string, string | number>) => string;

/**
 * Denetimin gerekçe kodları -> etiket. Kod listesi sunucuda kapalıdır
 * (moderation.py); tanımadığımız bir kod gelirse ham kodu basarız, böylece
 * sunucu yeni bir kategori eklediğinde panel kırılmaz.
 */
const modReasonKeys: Record<string, TranslationKey> = {
  kufur: "admin.modProfanity",
  hakaret: "admin.modInsult",
  nefret_soylemi: "admin.modHate",
  cinsel_icerik: "admin.modSexual",
  taciz: "admin.modHarassment",
  dolandiricilik: "admin.modScam",
  site_disi_yonlendirme: "admin.modOffsite",
  iletisim_bilgisi: "admin.modContact",
};

const doneKeys: Record<AdminActionKind, TranslationKey> = {
  resolve: "admin.doneResolve",
  reopen: "admin.doneReopen",
  removeListing: "admin.doneRemoveListing",
  removeMessage: "admin.doneRemoveMessage",
  restoreListing: "admin.doneRestoreListing",
  restoreMessage: "admin.doneRestoreMessage",
  clear: "admin.doneClear",
  suspend: "admin.doneSuspend",
  unsuspend: "admin.doneUnsuspend",
};

/**
 * Eylem başarıyla döndükten SONRA hangi cümlenin basılacağı.
 *
 * Saf fonksiyon olarak ayrıldı çünkü buradaki tek soru "istek 200 döndü mü"
 * DEĞİL, "sunucu gerçekten ne yaptı" sorusudur ve üç ayrı yanıtı vardır.
 * 200 dönen bir geri alma isteği kaydı HİÇ DEĞİŞTİRMEMİŞ olabilir; hepsine
 * aynı "başarılı" cümlesini basmak kullanıcıya olmamış bir şeyi olmuş gibi
 * göstermek olur. Sıra önemlidir: en dar durum en başta.
 */
export const restoreOutcome = (
  kind: AdminActionKind,
  data: Partial<RestoreResult>,
): { key: TranslationKey; tone: "success" | "warning" } => {
  // 1) Sunucu kayda HİÇ dokunmadı (mesajın özgün metni hiç saklanmamış).
  //    Kayıt kaldırılmış kalır ve Kaldırılanlar kuyruğunda görünmeye devam
  //    eder — "geri alındı" demek yalan olurdu.
  if (data.restored === false) {
    return { key: "admin.doneRestoreMessageUnrecoverable", tone: "warning" };
  }
  // 2) Kayıt geri alındı ama saklanan metin çözülemiyor (anahtar kaybolmuş
  //    ya da dönmüş): "metin geri kondu" demek yalan olurdu.
  if (data.content_restored === false) {
    return { key: "admin.doneRestoreMessageNoText", tone: "warning" };
  }
  // 3) Kaldırma geri alındı ama ilan yayına girmedi: sahibi onu zaten kendi
  //    kapatmıştı. (Yalnız restoreListing'de sorulur; reviewFlagged yanıtı da
  //    is_active taşır ve "kaldırdım" sonrası false olur — o bir uyarı değil,
  //    beklenen sonuçtur.)
  if (kind === "restoreListing" && data.is_active === false) {
    return { key: "admin.doneRestoreListingStillClosed", tone: "warning" };
  }
  return { key: doneKeys[kind], tone: "success" };
};

/** Panelden başlatılan, onay penceresinden geçen eylem. */
type AdminAction =
  | { kind: "resolve"; label: string; reportId: number }
  | { kind: "reopen"; label: string; reportId: number }
  | { kind: "removeListing"; label: string; itemId: number }
  | { kind: "removeMessage"; label: string; itemId: number }
  // staysClosed: ilan kaldırılmadan önce zaten kapalıydı; geri alma onu
  // yayına sokmaz. Onay penceresi bunu eylemden ÖNCE söyler.
  | { kind: "restoreListing"; label: string; itemId: number; staysClosed: boolean }
  // unrecoverable: mesajın özgün metni hiç saklanmamış; geri alma bu kayda
  // dokunamaz (kayıt Kaldırılanlar kuyruğunda kalır). Onay penceresi bunu da
  // eylemden ÖNCE söyler.
  | { kind: "restoreMessage"; label: string; itemId: number; unrecoverable: boolean }
  | { kind: "clear"; label: string; itemKind: FlaggedKind; itemId: number }
  | { kind: "suspend"; label: string; userId: number }
  | { kind: "unsuspend"; label: string; userId: number };

type Tab = "reports" | "flagged" | "suspended";

/**
 * Sunucunun içerik yerine yazdığı dilden bağımsız işaretleri kendi dilimize
 * çevirir; geri kalan metin olduğu gibi gösterilir.
 */
const contentText = (raw: string, t: Translate) =>
  raw === REMOVED_CONTENT
    ? t("admin.removedContent")
    : raw === UNREADABLE_CONTENT
      ? t("admin.unreadableContent")
      : raw;

const fmtDateTime = (iso: string, locale: string) =>
  parseUtc(iso).toLocaleString(locale, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });

// ---- küçük ortak parçalar ----

const Chip = ({ children, tone = "muted" }: { children: React.ReactNode; tone?: "muted" | "warn" | "danger" | "ok" }) => {
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

const Segmented = <V extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: V; label: string }[];
  value: V;
  onChange: (v: V) => void;
}) => (
  <div className="flex rounded-xl border border-border overflow-hidden">
    {options.map(opt => (
      <button
        key={opt.value}
        onClick={() => onChange(opt.value)}
        className={`flex-1 py-2.5 text-xs font-medium transition-all ${
          value === opt.value ? "bg-primary text-primary-foreground" : "bg-card text-foreground hover:bg-muted"
        }`}
      >
        {opt.label}
      </button>
    ))}
  </div>
);

const EmptyState = ({ icon: Icon, title, desc }: { icon: typeof Flag; title: string; desc: string }) => (
  <div className="text-center py-16 animate-fade-in">
    <div className="w-20 h-20 rounded-3xl bg-lavender/50 flex items-center justify-center mx-auto mb-4">
      <Icon className="w-9 h-9 text-primary" />
    </div>
    <p className="font-medium text-foreground">{title}</p>
    <p className="text-sm text-muted-foreground mt-1">{desc}</p>
  </div>
);

const StatTile = ({ value, label }: { value: string; label: string }) => (
  <div className="card-listing p-3 text-center">
    <p className="text-xl font-extrabold text-foreground tabular-nums">{value}</p>
    <p className="text-[10px] text-muted-foreground leading-tight mt-0.5">{label}</p>
  </div>
);

/** Denetim gerekçesi kodlarını ("kufur:siktir") etiketlere çevirip çipler basar. */
const FlagReasons = ({ reasons }: { reasons: string[] }) => {
  const { t } = useI18n();
  // Aynı kategori birden çok detayla gelebilir; kategori bazında tekilleştir.
  const categories = Array.from(new Set(reasons.map(r => r.split(":")[0])));
  return (
    <div>
      <p className="text-[11px] font-semibold text-foreground mb-1.5">{t("admin.flagReasonsLabel")}</p>
      {categories.length === 0 ? (
        <p className="text-xs text-muted-foreground">{t("admin.flagReasonsNone")}</p>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {categories.map(code => {
            const key = modReasonKeys[code];
            return (
              <Chip key={code} tone="warn">
                {key ? t(key) : code}
              </Chip>
            );
          })}
        </div>
      )}
    </div>
  );
};

const ActionButton = ({
  label,
  onClick,
  destructive = false,
}: {
  label: string;
  onClick: () => void;
  destructive?: boolean;
}) => (
  <button
    onClick={onClick}
    className={`h-9 px-4 rounded-full text-xs font-bold transition-all active:scale-95 ${
      destructive
        ? "bg-destructive/10 text-destructive hover:bg-destructive hover:text-destructive-foreground"
        : "bg-primary/10 text-primary hover:bg-primary hover:text-primary-foreground"
    }`}
  >
    {label}
  </button>
);

// ---- bildirim kartı ----

const targetTitleKeys = {
  listing: "admin.targetListing",
  user: "admin.targetUser",
  message: "admin.targetMessage",
} as const;

const ReportCard = ({ report, onAction }: { report: AdminReport; onAction: (a: AdminAction) => void }) => {
  const { t, locale } = useI18n();
  const target = report.target;
  const reasonKey = reportReasonKey(report.reason);
  const reasonLabel = reasonKey ? t(reasonKey) : report.reason;

  // Onay penceresinde gösterilecek kısa hedef adı.
  const targetLabel =
    target.deleted
      ? `${t(targetTitleKeys[target.kind])} #${target.id}`
      : target.kind === "listing"
        ? (target.title ?? `#${target.id}`)
        : target.kind === "user"
          ? (target.name ?? `#${target.id}`)
          : contentText(target.content ?? "", t).slice(0, 60);

  return (
    <div className="card-listing p-5 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-semibold text-sm text-foreground">{reasonLabel}</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {t("admin.reportedBy", { name: report.reporter_name })} · {fmtDateTime(report.created_at, locale)}
          </p>
        </div>
        <Chip tone={report.resolved ? "ok" : "danger"}>
          {report.resolved ? t("admin.badgeResolved") : t("admin.badgeOpen")}
        </Chip>
      </div>

      {report.note && (
        <div>
          <p className="text-[11px] font-semibold text-foreground">{t("admin.reportNote")}</p>
          <p className="text-sm text-muted-foreground break-words">{report.note}</p>
        </div>
      )}

      {/* Bildirilen içerik */}
      <div className="rounded-2xl bg-muted/50 p-3 space-y-1.5">
        <div className="flex flex-wrap items-center gap-1.5">
          <Chip>{t(targetTitleKeys[target.kind])}</Chip>
          {!target.deleted && target.kind === "listing" && target.is_flagged && (
            <Chip tone="warn">{t("admin.badgeFlagged")}</Chip>
          )}
          {!target.deleted && target.kind === "listing" && target.is_active === false && (
            <Chip tone="danger">{t("admin.badgeUnpublished")}</Chip>
          )}
          {!target.deleted && target.kind === "message" && target.is_flagged && (
            <Chip tone="warn">{t("admin.badgeFlagged")}</Chip>
          )}
          {!target.deleted && target.kind === "user" && target.is_suspended && (
            <Chip tone="danger">{t("admin.badgeSuspended")}</Chip>
          )}
        </div>

        {target.deleted ? (
          <p className="text-xs text-muted-foreground">{t("admin.targetDeleted")}</p>
        ) : target.kind === "listing" ? (
          <>
            <p className="text-sm font-medium text-foreground break-words">{target.title}</p>
            <p className="text-xs text-muted-foreground">
              {target.district ? `${target.district} · ` : ""}
              {t("admin.ownerLabel", { name: target.owner_name ?? "" })}
            </p>
          </>
        ) : target.kind === "user" ? (
          <>
            <p className="text-sm font-medium text-foreground break-words">{target.name}</p>
            <p className="text-xs text-muted-foreground">{target.university || t("admin.noUniversity")}</p>
          </>
        ) : (
          <>
            <p className="text-sm text-foreground break-words">{contentText(target.content ?? "", t)}</p>
            <p className="text-xs text-muted-foreground">
              {t("admin.senderLabel", { name: target.sender_name ?? "" })} ·{" "}
              {t("admin.matchLabel", { id: target.match_id ?? 0 })}
            </p>
          </>
        )}
      </div>

      {report.resolution_note && (
        <div>
          <p className="text-[11px] font-semibold text-foreground">{t("admin.resolutionNote")}</p>
          <p className="text-sm text-muted-foreground break-words">{report.resolution_note}</p>
        </div>
      )}

      <div className="flex flex-wrap gap-2 pt-1">
        {report.resolved ? (
          <ActionButton
            label={t("admin.actionReopen")}
            onClick={() => onAction({ kind: "reopen", label: targetLabel, reportId: report.id })}
          />
        ) : (
          <ActionButton
            label={t("admin.actionResolve")}
            onClick={() => onAction({ kind: "resolve", label: targetLabel, reportId: report.id })}
          />
        )}

        {/* Hedefe doğrudan uygulanan kararlar; silinmiş hedefte gösterilmez. */}
        {!target.deleted && target.kind === "listing" && target.is_active !== false && (
          <ActionButton
            destructive
            label={t("admin.actionRemoveListing")}
            onClick={() => onAction({ kind: "removeListing", label: targetLabel, itemId: target.id })}
          />
        )}
        {!target.deleted && target.kind === "message" && target.content !== REMOVED_CONTENT && (
          <ActionButton
            destructive
            label={t("admin.actionRemoveMessage")}
            onClick={() => onAction({ kind: "removeMessage", label: targetLabel, itemId: target.id })}
          />
        )}
        {!target.deleted && target.kind === "user" && (
          target.is_suspended ? (
            <ActionButton
              label={t("admin.actionUnsuspend")}
              onClick={() => onAction({ kind: "unsuspend", label: targetLabel, userId: target.id })}
            />
          ) : (
            <ActionButton
              destructive
              label={t("admin.actionSuspend")}
              onClick={() => onAction({ kind: "suspend", label: targetLabel, userId: target.id })}
            />
          )
        )}
      </div>
    </div>
  );
};

// ---- işaretlenen içerik kartı ----

const FlaggedCard = ({
  item,
  status,
  onAction,
}: {
  item: FlaggedItem;
  status: FlaggedStatus;
  onAction: (a: AdminAction) => void;
}) => {
  const { t, locale } = useI18n();
  const label = item.kind === "listing" ? (item.title ?? `#${item.id}`) : contentText(item.content, t).slice(0, 60);
  // "Kaldırılanlar" kuyruğunda satır zaten yönetici kararıyla kaldırılmıştır;
  // sunucu bu kuyrukta mesajın ÖZGÜN metnini döndürür (yönetici neyi geri
  // alacağını görmeden karar veremez).
  const removed = status === "removed";
  // Kaldırılan ilan geri alınınca KALDIRILMADAN ÖNCEKİ hâline döner. Sahibi
  // onu zaten kendi kapatmışsa geri alma yayına sokmaz — yönetici bunu
  // düğmeye basmadan önce görmeli. null = sunucu bu bilgiyi tutmadan önce
  // kaldırılmış eski kayıt; orada eski davranış (yayına al) geçerli.
  const staysClosed = removed && item.kind === "listing" && item.active_before_removal === false;
  // Kaldırılanlar kuyruğunda sunucu mesajın ÖZGÜN metnini döndürür. Metin
  // yerine sabitin KENDİSİ geliyorsa saklanmış bir özgün metin hiç yok
  // (bu sütunlar eklenmeden önce kaldırılmış eski kayıt): "geri al" bu kayda
  // dokunamaz. Yönetici bunu düğmeye basmadan önce görmeli.
  //
  // Sabitin kullanıcı metniyle karışma ihtimali yok: kullanıcı bu dizeyi
  // gönderemiyor (sunucu 422 ile reddediyor, bkz. moderation.SYSTEM_MARKERS).
  const textUnrecoverable =
    removed && item.kind === "message" && item.content === REMOVED_CONTENT;

  return (
    <div className="card-listing p-5 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5 mb-1">
            <Chip>{t(item.kind === "listing" ? "admin.targetListing" : "admin.targetMessage")}</Chip>
            {/* Rozet her iki kuyrukta da gösterilir: "Kaldırılanlar"da ilanın
                yayında olmadığını görmek kararın kendisi kadar önemli. */}
            {item.is_active === false && <Chip tone="danger">{t("admin.badgeUnpublished")}</Chip>}
          </div>
          {item.title && <p className="font-semibold text-sm text-foreground break-words">{item.title}</p>}
          <p className="text-xs text-muted-foreground mt-0.5">
            {item.kind === "listing"
              ? `${item.district ? `${item.district} · ` : ""}${t("admin.ownerLabel", { name: item.author_name ?? "" })}`
              : `${t("admin.senderLabel", { name: item.author_name ?? "" })} · ${t("admin.matchLabel", { id: item.match_id ?? 0 })}`}
          </p>
        </div>
        <Chip tone={removed ? "danger" : "warn"}>
          {t(removed ? "admin.badgeRemoved" : "admin.badgeFlagged")}
        </Chip>
      </div>

      <p className="text-sm text-foreground break-words rounded-2xl bg-muted/50 p-3">
        {contentText(item.content, t)}
      </p>

      {/* Kaldırılan içerik denetim işareti taşımayabilir (karar rapordan da
          verilebiliyor); gerekçe yoksa "kaydedilmemiş" demek yanıltıcı olur. */}
      {(!removed || item.flag_reasons.length > 0) && <FlagReasons reasons={item.flag_reasons} />}

      {staysClosed && (
        <div className="rounded-2xl border border-destructive/30 bg-destructive/5 px-3 py-2">
          <p className="text-xs text-destructive">{t("admin.staysClosedWarn")}</p>
        </div>
      )}

      {textUnrecoverable && (
        <div className="rounded-2xl border border-destructive/30 bg-destructive/5 px-3 py-2">
          <p className="text-xs text-destructive">{t("admin.textUnrecoverableWarn")}</p>
        </div>
      )}

      {removed && item.review_note && (
        <div>
          <p className="text-[11px] font-semibold text-foreground">{t("admin.resolutionNote")}</p>
          <p className="text-sm text-muted-foreground break-words">{item.review_note}</p>
        </div>
      )}

      <p className="text-[11px] text-muted-foreground">
        {fmtDateTime(item.created_at, locale)}
        {removed && item.reviewed_at
          ? ` · ${t("admin.removedAt", { date: fmtDateTime(item.reviewed_at, locale) })}`
          : ""}
      </p>

      <div className="flex flex-wrap gap-2 pt-1">
        {removed ? (
          <ActionButton
            label={t("admin.actionRestore")}
            onClick={() =>
              onAction(
                item.kind === "listing"
                  ? { kind: "restoreListing", label, itemId: item.id, staysClosed }
                  : {
                      kind: "restoreMessage",
                      label,
                      itemId: item.id,
                      unrecoverable: textUnrecoverable,
                    },
              )
            }
          />
        ) : (
          <>
            <ActionButton
              label={t("admin.actionClear")}
              onClick={() => onAction({ kind: "clear", label, itemKind: item.kind, itemId: item.id })}
            />
            <ActionButton
              destructive
              label={t("admin.actionRemove")}
              onClick={() =>
                onAction(
                  item.kind === "listing"
                    ? { kind: "removeListing", label, itemId: item.id }
                    : { kind: "removeMessage", label, itemId: item.id },
                )
              }
            />
          </>
        )}
      </div>
    </div>
  );
};

// ---- askıdaki kullanıcı kartı ----

const SuspendedCard = ({ row, onAction }: { row: AdminUserRow; onAction: (a: AdminAction) => void }) => {
  const { t, locale } = useI18n();
  return (
    <div className="card-listing p-5 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-semibold text-sm text-foreground break-words">{row.name}</p>
          {/* Sunucu e-postayı yalnızca askıdaki hesaplar için döner. */}
          {row.email && <p className="text-xs text-muted-foreground break-all">{row.email}</p>}
          <p className="text-xs text-muted-foreground">{row.university || t("admin.noUniversity")}</p>
        </div>
        <div className="flex flex-col items-end gap-1.5 shrink-0">
          <Chip tone="danger">{t("admin.badgeSuspended")}</Chip>
          {row.is_admin && <Chip tone="ok">{t("admin.badgeAdmin")}</Chip>}
        </div>
      </div>

      <div className="rounded-2xl bg-muted/50 p-3 space-y-1">
        <p className="text-xs text-foreground break-words">
          {row.suspended_reason
            ? t("admin.suspendedReason", { reason: row.suspended_reason })
            : t("admin.suspendedNoReason")}
        </p>
        {row.suspended_at && (
          <p className="text-[11px] text-muted-foreground">
            {t("admin.suspendedAt", { date: fmtDateTime(row.suspended_at, locale) })}
          </p>
        )}
      </div>

      <ActionButton
        label={t("admin.actionUnsuspend")}
        onClick={() => onAction({ kind: "unsuspend", label: row.name, userId: row.id })}
      />
    </div>
  );
};

// ---- panel ----

const Admin = () => {
  const { isLoggedIn, user } = useAuth();
  const { t, n } = useI18n();
  const queryClient = useQueryClient();

  const [tab, setTab] = useState<Tab>("reports");
  const [reportStatus, setReportStatus] = useState<AdminReportStatus>("open");
  const [flaggedKind, setFlaggedKind] = useState<FlaggedKind | "all">("all");
  const [flaggedStatus, setFlaggedStatus] = useState<FlaggedStatus>("pending");
  const [action, setAction] = useState<AdminAction | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // `user` oturum açıkken asenkron dolar; yönetici olmadığı KESİNLEŞENE kadar
  // yönlendirme yapmayız, yoksa sayfa yenilemesinde panel bir an kaçırılır.
  const isAdmin = user?.is_admin === true;

  const summary = useQuery({
    queryKey: ["admin", "summary"],
    queryFn: fetchAdminSummary,
    enabled: isAdmin,
  });
  const reports = useQuery({
    queryKey: ["admin", "reports", reportStatus],
    queryFn: () => fetchAdminReports(reportStatus),
    enabled: isAdmin && tab === "reports",
  });
  const flagged = useQuery({
    queryKey: ["admin", "flagged", flaggedKind, flaggedStatus],
    queryFn: () => fetchFlagged(flaggedKind, flaggedStatus),
    enabled: isAdmin && tab === "flagged",
  });
  const suspended = useQuery({
    queryKey: ["admin", "users", "suspended"],
    queryFn: () => fetchAdminUsers(true),
    enabled: isAdmin && tab === "suspended",
  });

  const mutation = useMutation({
    mutationFn: ({ a, note }: { a: AdminAction; note: string }) => {
      switch (a.kind) {
        case "resolve":
          return resolveAdminReport(a.reportId, true, note);
        case "reopen":
          return resolveAdminReport(a.reportId, false);
        case "removeListing":
          return reviewFlagged("listing", a.itemId, "remove", note);
        case "removeMessage":
          return reviewFlagged("message", a.itemId, "remove", note);
        case "restoreListing":
          return restoreRemoved("listing", a.itemId, note);
        case "restoreMessage":
          return restoreRemoved("message", a.itemId, note);
        case "clear":
          return reviewFlagged(a.itemKind, a.itemId, "clear", note);
        case "suspend":
          return suspendUser(a.userId, note);
        case "unsuspend":
          return unsuspendUser(a.userId);
      }
    },
    onSuccess: (data, { a }) => {
      // Panelin tüm listeleri + özet tazelensin; askı/kaldırma kararı
      // yöneticinin kendi ilan ve eşleşme listelerini de değiştirir.
      queryClient.invalidateQueries({ queryKey: ["admin"] });
      queryClient.invalidateQueries({ queryKey: ["listings"] });
      queryClient.invalidateQueries({ queryKey: ["matches"] });
      // Sunucunun GERÇEKTE ne yaptığına göre cümle seçilir; karar mantığı
      // restoreOutcome'da ve ayrıca test edilir.
      const { key, tone } = restoreOutcome(a.kind, data as Partial<RestoreResult>);
      (tone === "warning" ? toast.warning : toast.success)(t(key));
      setAction(null);
    },
    onError: err => {
      // Sunucunun açıklaması (400/403/404) olduğu gibi gösterilir.
      const message = err instanceof Error ? err.message : t("common.error");
      setActionError(message);
      toast.error(t("admin.actionFailed"), { description: message });
    },
  });

  const ask = (a: AdminAction) => {
    setActionError(null);
    setAction(a);
  };

  if (!isLoggedIn) return <Navigate to="/login" replace />;
  if (user !== null && !user.is_admin) return <Navigate to="/" replace />;

  const s = summary.data;
  const listQuery = tab === "reports" ? reports : tab === "flagged" ? flagged : suspended;

  // "Tümü" dışında bir tür seçiliyken kuyruğun boş olması YALNIZCA o filtre
  // için geçerlidir; sunucu istenen türü süzerek döndürür (GET /flagged?kind=).
  // "Hiç içerik kalmadı" demek diğer türde bekleyen kaydı yok saymak olurdu.
  const flaggedFiltered = flaggedKind !== "all";
  const flaggedEmptyTitle: TranslationKey = flaggedFiltered
    ? "admin.emptyFiltered"
    : flaggedStatus === "removed"
      ? "admin.emptyRemoved"
      : "admin.emptyFlagged";
  const flaggedEmptyDesc: TranslationKey =
    flaggedStatus === "removed"
      ? flaggedFiltered
        ? "admin.emptyRemovedFilteredDesc"
        : "admin.emptyRemovedDesc"
      : flaggedFiltered
        ? "admin.emptyFlaggedFilteredDesc"
        : "admin.emptyFlaggedDesc";

  return (
    <div className="min-h-screen bg-background pb-20">
      <AppHeader
        title={t("admin.title")}
        showBack
        rightAction={
          <button
            onClick={() => queryClient.invalidateQueries({ queryKey: ["admin"] })}
            aria-label={t("admin.refresh")}
            title={t("admin.refresh")}
            className="w-10 h-10 rounded-full bg-background flex items-center justify-center text-foreground hover:bg-muted transition-colors shrink-0"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        }
      />

      <div className="px-6 py-4 space-y-4">
        <p className="text-sm text-muted-foreground">{t("admin.subtitle")}</p>

        {/* Özet */}
        {summary.isError ? (
          <p className="text-sm text-destructive">{t("admin.summaryFailed")}</p>
        ) : (
          s && (
            <div className="grid grid-cols-3 gap-2">
              <StatTile value={n(s.open_reports)} label={t("admin.openReports")} />
              <StatTile value={n(s.flagged_listings)} label={t("admin.flaggedListings")} />
              <StatTile value={n(s.flagged_messages)} label={t("admin.flaggedMessages")} />
              <StatTile value={n(s.suspended_users)} label={t("admin.suspendedUsers")} />
              <StatTile value={n(s.total_users)} label={t("admin.totalUsers")} />
              <StatTile value={n(s.active_listings)} label={t("admin.activeListings")} />
            </div>
          )
        )}

        {/* Sekmeler */}
        <Segmented<Tab>
          value={tab}
          onChange={setTab}
          options={[
            { value: "reports", label: t("admin.tabReports") },
            { value: "flagged", label: t("admin.tabFlagged") },
            { value: "suspended", label: t("admin.tabSuspended") },
          ]}
        />

        {/* Sekmeye özel filtre */}
        {tab === "reports" && (
          <Segmented<AdminReportStatus>
            value={reportStatus}
            onChange={setReportStatus}
            options={[
              { value: "open", label: t("admin.statusOpen") },
              { value: "resolved", label: t("admin.statusResolved") },
              { value: "all", label: t("admin.statusAll") },
            ]}
          />
        )}
        {tab === "flagged" && (
          <div className="space-y-2">
            {/* "Kaldırılanlar" olmadan yönetici kararı geri alınamazdı:
                kaldırılan içerik hiçbir kuyrukta görünmüyordu. */}
            <Segmented<FlaggedStatus>
              value={flaggedStatus}
              onChange={setFlaggedStatus}
              options={[
                { value: "pending", label: t("admin.flagStatusPending") },
                { value: "removed", label: t("admin.flagStatusRemoved") },
              ]}
            />
            <Segmented<FlaggedKind | "all">
              value={flaggedKind}
              onChange={setFlaggedKind}
              options={[
                { value: "all", label: t("admin.kindAll") },
                { value: "listing", label: t("admin.kindListing") },
                { value: "message", label: t("admin.kindMessage") },
              ]}
            />
          </div>
        )}

        {/* Liste */}
        {listQuery.isPending ? (
          <p className="text-center text-sm text-muted-foreground py-12">{t("common.loading")}</p>
        ) : listQuery.isError ? (
          <p className="text-center text-sm text-destructive py-12">{t("admin.loadFailed")}</p>
        ) : (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-3">
            {tab === "reports" &&
              (reports.data?.length
                ? reports.data.map(r => <ReportCard key={r.id} report={r} onAction={ask} />)
                : (
                  <EmptyState
                    icon={Flag}
                    title={t(reportStatus === "open" ? "admin.emptyReports" : "admin.emptyReportsFiltered")}
                    desc={t(reportStatus === "open" ? "admin.emptyReportsDesc" : "admin.emptyReportsFilteredDesc")}
                  />
                ))}

            {tab === "flagged" &&
              (flagged.data?.length
                ? flagged.data.map(item => (
                    <FlaggedCard
                      key={`${item.kind}-${item.id}`}
                      item={item}
                      status={flaggedStatus}
                      onAction={ask}
                    />
                  ))
                : (
                  <EmptyState
                    icon={ShieldCheck}
                    title={t(flaggedEmptyTitle)}
                    desc={t(flaggedEmptyDesc)}
                  />
                ))}

            {tab === "suspended" &&
              (suspended.data?.length
                ? suspended.data.map(row => <SuspendedCard key={row.id} row={row} onAction={ask} />)
                : <EmptyState icon={UserX} title={t("admin.emptySuspended")} desc={t("admin.emptySuspendedDesc")} />)}
          </motion.div>
        )}
      </div>

      <AdminActionDialog
        open={action !== null}
        // Kapanış animasyonu sırasında `action` null olur; son biçim korunsun.
        kind={action?.kind ?? "resolve"}
        targetLabel={action?.label}
        // Geri alma ilanı yayına sokmayacaksa onay penceresi bunu ÖNCEDEN
        // söyler; yönetici "yeniden yayına alıyorum" sanarak onaylamasın.
        warning={
          action?.kind === "restoreListing" && action.staysClosed
            ? t("admin.staysClosedWarn")
            : action?.kind === "restoreMessage" && action.unrecoverable
              ? t("admin.textUnrecoverableWarn")
              : null
        }
        pending={mutation.isPending}
        error={actionError}
        onClose={() => {
          if (mutation.isPending) return;
          setAction(null);
          setActionError(null);
        }}
        onConfirm={note => {
          if (action) mutation.mutate({ a: action, note });
        }}
      />

      <BottomNav />
    </div>
  );
};

export default Admin;
