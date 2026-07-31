/**
 * FastAPI backend istemcisi.
 *
 * Backend (backend/ klasörü) adil fiyat modelini, bütçe ısı haritasını ve
 * raylı sistem tabanlı alternatif semt önerisini servis eder. Adres
 * VITE_API_URL ile ayarlanır (bkz. .env.example).
 */

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
    throw new Error(
      (data && typeof data.detail === "string" && data.detail) ||
        `İstek başarısız (${res.status})`,
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
  summary: Record<StatusKey, number>;
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

export const fetchListings = (params?: {
  type?: ListingPayload["type"];
  district?: string;
  mine?: boolean;
}) => {
  const query = new URLSearchParams();
  if (params?.type) query.set("type", params.type);
  if (params?.district) query.set("district", params.district);
  if (params?.mine) query.set("mine", "true");
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
}

export interface UserUpdate {
  name?: string;
  gender?: string;
  birth_year?: number;
  university?: string;
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

export const fetchMe = () => getJSON<ApiUser>("/api/auth/me");

export const updateMe = (payload: UserUpdate) =>
  request<ApiUser>("/api/auth/me", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });

export const logoutApi = () =>
  request<void>("/api/auth/logout", { method: "POST" });

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
        `Yükleme başarısız (${res.status})`,
    );
  }
  return data as { url: string };
};
