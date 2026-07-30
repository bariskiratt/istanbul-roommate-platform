/**
 * FastAPI backend istemcisi.
 *
 * Backend (backend/ klasörü) adil fiyat modelini, bütçe ısı haritasını ve
 * raylı sistem tabanlı alternatif semt önerisini servis eder. Adres
 * VITE_API_URL ile ayarlanır (bkz. .env.example).
 */

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(
      (detail && typeof detail.detail === "string" && detail.detail) ||
        `İstek başarısız (${res.status})`,
    );
  }
  return res.json();
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error(
      (data && typeof data.detail === "string" && data.detail) ||
        `İstek başarısız (${res.status})`,
    );
  }
  return data as T;
}

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
}

export interface EstimateResponse {
  fair_low: number;
  fair_mid: number;
  fair_high: number;
  median_error_pct: number;
  known_neighborhood: boolean;
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
}

export const createListing = (payload: ListingPayload) =>
  postJSON<ApiListing>("/api/listings", payload);

export const fetchListings = (params?: {
  type?: ListingPayload["type"];
  district?: string;
}) => {
  const query = new URLSearchParams();
  if (params?.type) query.set("type", params.type);
  if (params?.district) query.set("district", params.district);
  const qs = query.toString();
  return getJSON<ApiListing[]>(`/api/listings${qs ? `?${qs}` : ""}`);
};
