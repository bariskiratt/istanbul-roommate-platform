/**
 * FastAPI backend istemcisi.
 *
 * Backend (backend/ klasörü) adil fiyat modelini, bütçe ısı haritasını ve
 * raylı sistem tabanlı alternatif semt önerisini servis eder. Adres
 * VITE_API_URL ile ayarlanır (bkz. .env.example).
 */

import { translate } from "@/i18n";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

// ---- Token saklama ----

const TOKEN_KEY = "roommatch_token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (token: string) => localStorage.setItem(TOKEN_KEY, token);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Sunucunun döndürdüğü hata. `message` her zaman kullanıcıya gösterilebilir
 * (sunucu `detail` alanı ya da genel bir metin); `status` çağıranın hatayı
 * ayırt etmesi için taşınır — ör. 422 = moderasyon reddi.
 */
export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...authHeaders(),
      ...init?.headers,
    },
  });
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new ApiError(
      (data && typeof data.detail === "string" && data.detail) ||
        translate("common.requestFailed", { status: res.status }),
      res.status,
    );
  }
  return data as T;
}

const getJSON = <T>(path: string) => request<T>(path);

const postJSON = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body) });

// ---- Adil fiyat tahmini ----

export interface EstimateRequest {
  district: string;
  neighborhood: string;
  room: number;
  living_room?: number;
  area: number;
  age: number;
  floor: number;
  asking_price?: number;
  /** "room": istenen fiyat tek odanın payı (ev arkadaşı senaryosu). */
  basis?: "flat" | "room";
}

export interface EstimateResponse {
  fair_low: number;
  fair_mid: number;
  fair_high: number;
  /** Oda başına adil pay (daire kirası / yatak odası sayısı) */
  room_low: number;
  room_mid: number;
  room_high: number;
  room_share: number;
  median_error_pct: number;
  known_neighborhood: boolean;
  /** TÜFE endeksleme bilgisi */
  index_factor: number;
  data_period: string;
  indexed_to: string;
  basis: "flat" | "room";
  asking_price?: number;
  verdict?: "below" | "fair" | "above";
  deviation_pct?: number;
}

export const estimatePrice = (payload: EstimateRequest) =>
  postJSON<EstimateResponse>("/api/estimate", payload);

// İlçe -> mahalle listesi (form doldurmak için)
export const fetchLocations = () =>
  getJSON<Record<string, string[]>>("/api/locations");

// ---- Bütçe ısı haritası ----

export type StatusKey = "safe" | "borderline" | "expensive" | "nodata";

export interface HeatmapResponse {
  budget: number;
  statuses: StatusKey[];
  /** Az ilana dayanan (zayıf temsil) mahalleler — aynı sırada. */
  low_confidence: boolean[];
  summary: Record<StatusKey, number> & { low_confidence: number };
}

export const fetchGeojson = () =>
  getJSON<GeoJSON.FeatureCollection>("/api/geojson");

export const fetchHeatmap = (budget: number) =>
  getJSON<HeatmapResponse>(`/api/heatmap?budget=${budget}`);

export const fetchLegend = () =>
  getJSON<Record<StatusKey, { label: string; color: string }>>("/api/legend");

// ---- Alternatif semt önerisi ----

export interface AltPlace {
  id: number;
  name: string;
  district: string;
  price: number | null;
  walk_km: number;
  lat: number;
  lon: number;
  network_cost?: number;
  saving?: number | null;
}

export interface AlternativesResponse {
  target: AltPlace & { message?: string };
  reachable: boolean;
  budget?: number;
  recommendations: AltPlace[];
}

export const fetchAlternatives = (neighborhoodId: number, budget: number) =>
  getJSON<AlternativesResponse>(
    `/api/alternatives?neighborhood_id=${neighborhoodId}&budget=${budget}`,
  );

// ---- İlanlar ----

/**
 * Ev özellikleri. Anahtarlar backend sütunlarıyla birebir aynıdır; hem
 * `GET /api/listings?features=` filtresi hem de ilan gövdesi bunları kullanır.
 */
export const LISTING_FEATURES = [
  "furnished",
  "elevator",
  "parking",
  "internet_included",
  "heating_included",
  "balcony",
  "natural_gas",
] as const;

export type ListingFeature = (typeof LISTING_FEATURES)[number];

export interface ListingPayload {
  type: "ev_ilani" | "kisisel_ilan";
  title: string;
  description: string;
  district: string;
  photos: string[];
  // Ev ilanı
  rent?: number;
  room_count?: string;
  smoking_allowed?: boolean;
  pets_allowed?: boolean;
  // Ev özellikleri — belirtilmezse sunucuda null kalır ("bilinmiyor").
  // Yanıtta da null gelebilir, bu yüzden okurken `=== true` ile karşılaştır.
  furnished?: boolean;
  elevator?: boolean;
  parking?: boolean;
  internet_included?: boolean;
  heating_included?: boolean;
  balcony?: boolean;
  natural_gas?: boolean;
  // Kişisel ilan
  budget_min?: number;
  budget_max?: number;
}

export interface ApiListing extends ListingPayload {
  id: number;
  is_active: boolean;
  created_at: string;
  owner_id: number | null;
  owner_name: string | null;
  owner_university: string | null;
}

export const createListing = (payload: ListingPayload) =>
  postJSON<ApiListing>("/api/listings", payload);

export const updateListing = (id: number, payload: Partial<ListingPayload>) =>
  request<ApiListing>(`/api/listings/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });

export const deleteListing = (id: number) =>
  request<void>(`/api/listings/${id}`, { method: "DELETE" });

/** İlanın istediği oda payının adil aralıkla kıyası (ev arkadaşlığı bazlı). */
export interface ListingFairPrice {
  asking_price: number;
  verdict: "below" | "fair" | "above";
  deviation_pct: number;
  room_low: number;
  room_mid: number;
  room_high: number;
  flat_low: number;
  flat_mid: number;
  flat_high: number;
  bedrooms: number;
  occupants: number;
  shared_areas: string[];
  median_error_pct: number;
  data_period: string;
  indexed_to: string;
  district_level: boolean;
}

export const fetchListingFairPrice = (id: number) =>
  getJSON<ListingFairPrice>(`/api/listings/${id}/fair-price`);

export const fetchListings = (params?: {
  type?: ListingPayload["type"];
  district?: string;
  mine?: boolean;
  /** Kaydırılmış ve kendi ilanlarını gizler (deste için). */
  unswiped?: boolean;
  /** Hepsi işaretli olan ilanlar döner (VE mantığı). */
  features?: ListingFeature[];
}) => {
  const query = new URLSearchParams();
  if (params?.type) query.set("type", params.type);
  if (params?.district) query.set("district", params.district);
  if (params?.mine) query.set("mine", "true");
  if (params?.unswiped) query.set("unswiped", "true");
  if (params?.features?.length) query.set("features", params.features.join(","));
  const qs = query.toString();
  return getJSON<ApiListing[]>(`/api/listings${qs ? `?${qs}` : ""}`);
};

// ---- Kimlik doğrulama ----
// E-posta servisi bağlı olmadığı için OTP kodu dev modda yanıttaki
// dev_code alanında gelir; arayüz bunu kullanıcıya gösterir.

export interface ApiUser {
  id: number;
  email: string;
  verified: boolean;
  name: string;
  gender: string | null;
  birth_year: number | null;
  university: string | null;
  department: string | null;
  year: number | null;
  budget_min: number | null;
  budget_max: number | null;
  smoking: boolean | null;
  pets: boolean | null;
  alcohol: boolean | null;
  sleep_schedule: string | null;
  preferred_districts: string[];
  bio: string;
  photos: string[];
  created_at: string;
  is_admin: boolean;
}

export interface UserUpdate {
  name?: string;
  gender?: string;
  birth_year?: number;
  // university yok: e-posta alan adından otomatik atanır, elle değiştirilemez
  department?: string;
  year?: number;
  budget_min?: number;
  budget_max?: number;
  smoking?: boolean;
  pets?: boolean;
  alcohol?: boolean;
  sleep_schedule?: string;
  preferred_districts?: string[];
  bio?: string;
  photos?: string[];
}

export const registerUser = (email: string, password: string) =>
  postJSON<{ detail: string; dev_code?: string }>("/api/auth/register", {
    email,
    password,
  });

export const requestOtp = (email: string) =>
  postJSON<{ detail: string; dev_code?: string }>("/api/auth/request-otp", {
    email,
  });

export const verifyOtp = (email: string, code: string) =>
  postJSON<{ token: string; user: ApiUser }>("/api/auth/verify-otp", {
    email,
    code,
  });

export const loginWithPassword = (email: string, password: string) =>
  postJSON<{ token: string; user: ApiUser }>("/api/auth/login", {
    email,
    password,
  });

export const fetchMe = () => getJSON<ApiUser>("/api/auth/me");

/** Bölüm listesi (grup adı -> bölümler). Sabit liste, uzun süre cache'lenir. */
export const fetchDepartments = () =>
  getJSON<Record<string, string[]>>("/api/auth/departments");

export const updateMe = (payload: UserUpdate) =>
  request<ApiUser>("/api/auth/me", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });

export const logoutApi = () =>
  request<void>("/api/auth/logout", { method: "POST" });

/** Şifre değiştirir; sunucu tüm oturumları düşürür. */
export const changePassword = (currentPassword: string, newPassword: string) =>
  request<void>("/api/auth/change-password", {
    method: "POST",
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });

/** Hesabı ve tüm verilerini kalıcı olarak siler. */
export const deleteAccount = (password: string) =>
  request<void>("/api/auth/me", {
    method: "DELETE",
    body: JSON.stringify({ password }),
  });

// ---- Swipe ve eşleşme ----

export interface PublicUser {
  id: number;
  name: string;
  university: string | null;
  department: string | null;
  year: number | null;
  budget_min: number | null;
  budget_max: number | null;
  smoking: boolean | null;
  pets: boolean | null;
  alcohol: boolean | null;
  sleep_schedule: string | null;
  preferred_districts: string[];
  bio: string;
  photos: string[];
}

export interface SwipeResult {
  matched: boolean;
  match_id: number | null;
}

export interface ReceivedLike {
  swipe_id: number;
  user: PublicUser;
  listing_id: number;
  listing_title: string;
  created_at: string;
}

export interface Match {
  id: number;
  other_user: PublicUser;
  listing_id: number | null;
  listing_title: string | null;
  created_at: string;
  last_message: string | null;
  last_message_at: string | null;
}

export const postSwipe = (listingId: number, direction: "like" | "pass") =>
  postJSON<SwipeResult>("/api/swipes", { listing_id: listingId, direction });

export const fetchReceivedLikes = () =>
  getJSON<ReceivedLike[]>("/api/swipes/received");

export const respondToLike = (swipeId: number, accept: boolean) =>
  postJSON<SwipeResult>(`/api/swipes/${swipeId}/respond`, { accept });

export const fetchMatches = () => getJSON<Match[]>("/api/matches");

/**
 * Kendi kaydırma geçmişini siler; deste baştan gelir. Sunucu bu ucu YALNIZCA
 * yöneticilere açar (aksi halde 403). Eşleşmeler ve mesajlar korunur; silinen
 * yalnızca "like/pass" kararlarıdır.
 */
export const resetMyDeck = () =>
  request<{ deleted: number }>("/api/swipes/mine", { method: "DELETE" });

// ---- Mesajlaşma ----

export interface ChatMessage {
  id: number;
  match_id: number;
  sender_id: number;
  content: string;
  created_at: string;
}

export const fetchMessages = (matchId: number) =>
  getJSON<ChatMessage[]>(`/api/matches/${matchId}/messages`);

export const sendMessage = (matchId: number, content: string) =>
  postJSON<ChatMessage>(`/api/matches/${matchId}/messages`, { content });

// ---- Raporlama ----

export type ReportTargetType = "listing" | "user" | "message";

export interface ApiReport {
  id: number;
  reporter_id: number;
  target_type: string;
  target_id: number;
  reason: string;
  note: string | null;
  created_at: string;
  resolved: boolean;
  resolution_note: string | null;
}

/**
 * Sunucudaki kapalı sebep listesi ("spam", "taciz" …). Arayüz etiketleri
 * i18n'den gelir; listenin kendisi tek doğruluk kaynağı olarak sunucudadır.
 */
export const fetchReportReasons = () => getJSON<string[]>("/api/reports/reasons");

/** Not boşsa hiç gönderilmez; sunucu tarafında null kalır. */
export const postReport = (
  targetType: ReportTargetType,
  targetId: number,
  reason: string,
  note?: string,
) =>
  postJSON<ApiReport>("/api/reports", {
    target_type: targetType,
    target_id: targetId,
    reason,
    ...(note?.trim() ? { note: note.trim() } : {}),
  });

// ---- Yönetim paneli ----
// Tüm /api/admin/* uçları sunucuda require_admin ile korunur: girişsiz 401,
// yönetici olmayan 403 alır. Arayüz ayrıca sayfayı is_admin ile kapatır.

/**
 * Denetim tarafından içeriği kaldırılan mesajın yerine sunucunun yazdığı sabit.
 * Dilden bağımsız bir işarettir, kullanıcıya gösterilecek metin değildir —
 * arayüz bunu tanıyıp kendi dilindeki karşılığını basar.
 */
export const REMOVED_CONTENT = "[removed_by_moderation]";

/** Şifresi çözülemeyen mesajlar için sunucunun yazdığı sabit (aynı mantık). */
export const UNREADABLE_CONTENT = "[unreadable]";

export interface AdminSummary {
  open_reports: number;
  flagged_listings: number;
  flagged_messages: number;
  suspended_users: number;
  total_users: number;
  active_listings: number;
}

export type AdminReportStatus = "open" | "resolved" | "all";

/**
 * Rapor hedefinin özeti. `deleted: true` ise yalnızca kind/id/deleted gelir;
 * bu yüzden geri kalan alanlar isteğe bağlıdır.
 */
export interface AdminListingTarget {
  kind: "listing";
  id: number;
  deleted: boolean;
  title?: string;
  district?: string | null;
  is_active?: boolean;
  is_flagged?: boolean;
  owner_id?: number;
  owner_name?: string;
}

export interface AdminUserTarget {
  kind: "user";
  id: number;
  deleted: boolean;
  name?: string;
  university?: string | null;
  is_suspended?: boolean;
}

export interface AdminMessageTarget {
  kind: "message";
  id: number;
  deleted: boolean;
  /** Yalnızca raporlanan mesajın kendisi; sohbet geçmişi sunucudan hiç gelmez. */
  content?: string;
  sender_id?: number;
  sender_name?: string;
  match_id?: number;
  is_flagged?: boolean;
  created_at?: string;
}

export type AdminReportTarget = AdminListingTarget | AdminUserTarget | AdminMessageTarget;

export interface AdminReport {
  id: number;
  reason: string;
  note: string | null;
  created_at: string;
  resolved: boolean;
  resolution_note: string | null;
  resolved_by: number | null;
  resolved_at: string | null;
  reporter_id: number;
  reporter_name: string;
  target_type: ReportTargetType;
  target_id: number;
  /** Her zaman bir nesne döner; hedef silinmişse `deleted: true` olur. */
  target: AdminReportTarget;
}

export type FlaggedKind = "listing" | "message";

/**
 * İnceleme kuyrukları:
 * - "pending": denetimin işaretlediği, henüz karara bağlanmamış içerik.
 * - "removed": yöneticinin kaldırdığı içerik. Bu kuyruk kaldırılan kaydı
 *   BULUNABİLİR tutar; geri alma ancak böyle mümkün.
 */
export type FlaggedStatus = "pending" | "removed";

export interface FlaggedItem {
  kind: FlaggedKind;
  id: number;
  /** İlanda başlık, mesajda null. */
  title: string | null;
  /**
   * İlan açıklaması ya da çözülmüş mesaj metni. "removed" kuyruğunda mesajın
   * KALDIRILAN ÖZGÜN metni gelir — yönetici neyi geri alacağını görsün diye.
   */
  content: string;
  district: string | null;
  author_id: number | null;
  /** Yazar kaydı silinmişse null gelebilir. */
  author_name: string | null;
  match_id: number | null;
  is_active: boolean | null;
  /** Kaldırma kararı yöneticiden mi geldi (sahibinin kendi kapattığı ilan değil). */
  moderation_removed: boolean;
  /**
   * Yalnız ilanda ve yalnız "removed" kuyruğunda anlamlı: ilan KALDIRILMADAN
   * ÖNCE yayında mıydı. `false` ise kaldırma kararını geri almak ilanı yayına
   * SOKMAZ — sahibi onu zaten kendi kapatmıştı. Sunucu bu sütunu eklemeden
   * önce kaldırılmış kayıtlarda null gelir (önceki durum bilinmiyor).
   */
  active_before_removal: boolean | null;
  /** Denetimin gerekçe kodları ("iletisim_bilgisi:telefon" gibi). Eski kayıtlarda boş. */
  flag_reasons: string[];
  /** Sunucunun ürettiği Türkçe cümle; İngilizce arayüz kodlardan kendi metnini üretir. */
  flag_reasons_text: string | null;
  /** Kaldırma kararının izi; "removed" kuyruğunda dolu olur. */
  reviewed_by: number | null;
  reviewed_at: string | null;
  review_note: string | null;
  created_at: string;
}

export interface FlaggedReviewResult {
  kind: FlaggedKind;
  id: number;
  action: "clear" | "remove";
  is_flagged: boolean;
  is_active: boolean | null;
  moderation_removed: boolean;
  content_removed: boolean;
  reviewed_by: number;
  reviewed_at: string;
  review_note: string | null;
}

export interface RestoreResult {
  kind: FlaggedKind;
  id: number;
  /**
   * Kayda GERÇEKTEN dokunuldu mu.
   *
   * `false` YALNIZCA tek bir durumda döner: mesajın özgün metni hiç
   * saklanmamış (bu sütunlar eklenmeden önce kaldırılmış eski kayıt). Sunucu
   * o kaydı BİLEREK hiç değiştirmez — `moderation_removed` True kalır ve
   * satır "Kaldırılanlar" kuyruğunda bulunabilir olmayı sürdürür. Bayrağı
   * indirmek kaydı her listeden düşürür ve bir daha bulunamaz hâle getirirdi.
   *
   * Bu alan eskiden `true` sabiti olarak yazılmıştı; TypeScript `false`
   * ihtimalini eleyince arayüz hiç değişmemiş bir kayıt için "geri alındı"
   * diyordu. Sunucu sözleşmesi budur: boolean.
   */
  restored: boolean;
  /**
   * Yalnız ilanda dolu. Geri alma ilanı KALDIRMADAN ÖNCEKİ hâline döndürür:
   * `false` ise kaldırma kararı geri alındı ama ilan yayına GİRMEDİ, çünkü
   * sahibi onu zaten kendi kapatmıştı — arayüz bu durumda "yeniden yayında"
   * dememeli.
   */
  is_active: boolean | null;
  moderation_removed: boolean;
  /**
   * Yalnız mesajda dolu. Geri alınacak bir metin VAR MIYDI?
   * `false` ise kayıt hiç değiştirilmedi (bkz. `restored`); `true` ise metin
   * yerine kondu — ama okunabilirliği ayrı bir sorudur, `content_restored`e
   * bak.
   */
  content_recoverable: boolean | null;
  /**
   * Yalnız mesajda dolu. `true` ise metin gerçekten OKUNABİLİR biçimde geri
   * geldi. `false` ise metin geri gelmedi; arayüz metnin döndüğünü
   * söylememeli. İki ayrı sebebi olabilir ve ikisi AYNI cümleyle
   * anlatılamaz:
   *   - `content_recoverable: true`  -> metin yerine kondu ama çözülemiyor
   *     (anahtar kaybolmuş/dönmüş). Kayıt kuyruktan DÜŞTÜ.
   *   - `content_recoverable: false` -> saklanmış metin hiç yoktu. Kayıt
   *     kuyrukta KALDI, hiçbir şey değişmedi.
   */
  content_restored: boolean | null;
  reviewed_by: number | null;
  reviewed_at: string | null;
  review_note: string | null;
}

export interface AdminUserRow {
  id: number;
  /** Sunucu e-postayı YALNIZCA askıdaki hesaplar için döner; değilse null. */
  email: string | null;
  name: string;
  university: string | null;
  is_admin: boolean;
  is_suspended: boolean;
  suspended_at: string | null;
  suspended_reason: string | null;
  suspended_by: number | null;
  created_at: string;
}

export const fetchAdminSummary = () => getJSON<AdminSummary>("/api/admin/summary");

export const fetchAdminReports = (status: AdminReportStatus = "open") =>
  getJSON<AdminReport[]>(`/api/admin/reports?status=${status}`);

/**
 * `resolved: false` raporu açık kuyruğa geri alır; sunucu bu sırada karar
 * notunu da (resolved_by/resolved_at ile birlikte) siler.
 */
export const resolveAdminReport = (
  reportId: number,
  resolved: boolean,
  resolutionNote?: string,
) =>
  request<AdminReport>(`/api/admin/reports/${reportId}`, {
    method: "PATCH",
    body: JSON.stringify({
      resolved,
      ...(resolutionNote?.trim() ? { resolution_note: resolutionNote.trim() } : {}),
    }),
  });

export const fetchFlagged = (
  kind: FlaggedKind | "all" = "all",
  status: FlaggedStatus = "pending",
) => getJSON<FlaggedItem[]>(`/api/admin/flagged?kind=${kind}&status=${status}`);

/**
 * "clear" içeriği temiz sayar, "remove" ilanı yayından kaldırır / mesaj
 * içeriğini kaldırır. Satır hiçbir durumda silinmez. Uç işaretli olmayan
 * içerik için de çalışır (rapor satırındaki "yayından kaldır" bunu kullanır).
 */
export const reviewFlagged = (
  kind: FlaggedKind,
  itemId: number,
  action: "clear" | "remove",
  note?: string,
) =>
  postJSON<FlaggedReviewResult>(`/api/admin/flagged/${kind}/${itemId}/review`, {
    action,
    ...(note?.trim() ? { note: note.trim() } : {}),
  });

/**
 * Kaldırma kararını geri alır. İlan KALDIRILMADAN ÖNCEKİ hâline döner:
 * sahibi onu zaten kendi kapatmışsa kapalı kalır — yanıttaki `is_active`
 * hangisinin olduğunu söyler. Mesajda saklanan özgün metin sohbete geri
 * konur (`content_restored`). Yalnızca yöneticinin kaldırdığı kayıtta
 * çalışır; moderasyon kararı taşımayan kayıtta sunucu 400 döner.
 */
export const restoreRemoved = (kind: FlaggedKind, itemId: number, note?: string) =>
  postJSON<RestoreResult>(`/api/admin/${kind}/${itemId}/restore`, {
    ...(note?.trim() ? { note: note.trim() } : {}),
  });

/** `suspended` zorunludur; sunucu filtresiz listelemeyi kabul etmez (422). */
export const fetchAdminUsers = (suspended: boolean) =>
  getJSON<AdminUserRow[]>(`/api/admin/users?suspended=${suspended}`);

export const suspendUser = (userId: number, reason?: string) =>
  postJSON<AdminUserRow>(`/api/admin/users/${userId}/suspend`, {
    ...(reason?.trim() ? { reason: reason.trim() } : {}),
  });

export const unsuspendUser = (userId: number) =>
  request<AdminUserRow>(`/api/admin/users/${userId}/unsuspend`, { method: "POST" });

// ---- Fotoğraf yükleme ----

export const uploadPhoto = async (file: File): Promise<{ url: string }> => {
  const form = new FormData();
  form.append("file", file);
  // Content-Type elle verilmez; tarayıcı multipart sınırını kendisi ekler.
  const res = await fetch(`${BASE_URL}/api/uploads`, {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error(
      (data && typeof data.detail === "string" && data.detail) ||
        translate("common.uploadFailed", { status: res.status }),
    );
  }
  return data as { url: string };
};
