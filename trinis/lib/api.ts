// PATH: src/lib/api.ts
import axios, { AxiosInstance } from "axios";
import { getSession } from "next-auth/react";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

// ── Axios instance ────────────────────────────────────────────────────────
const api: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
});

// Attach JWT from NextAuth session on every request
api.interceptors.request.use(async (config) => {
  const session = await getSession();
  if (session?.user?.access_token) {
    config.headers.Authorization = `Bearer ${session.user.access_token}`;
  }
  return config;
});

// ── Auth ──────────────────────────────────────────────────────────────────
export const authApi = {
  login: (email: string, password: string) =>
    api.post("/auth/login", { email, password }),

  register: (data: {
    email: string;
    password: string;
    full_name: string;
    workspace_name: string;
  }) => api.post("/auth/register", data),

  me: () => api.get("/auth/me"),
};

// ── Tenant ────────────────────────────────────────────────────────────────
export const tenantApi = {
  get: () => api.get("/tenant"),
};

// ── Stores ────────────────────────────────────────────────────────────────
export const storesApi = {
  list: () => api.get("/stores"),

  initiateOAuth: (shop_domain: string) =>
    api.post("/stores/connect", null, { params: { shop_domain } }),

  disconnect: (storeId: string) => api.delete(`/stores/${storeId}`),
};

// ── Vendor configs ────────────────────────────────────────────────────────
export const vendorApi = {
  list: () => api.get("/vendors"),
  create: (data: Record<string, unknown>) => api.post("/vendors", data),
  update: (id: string, data: Record<string, unknown>) =>
    api.put(`/vendors/${id}`, data),
  delete: (id: string) => api.delete(`/vendors/${id}`),
};

// ── Jobs ──────────────────────────────────────────────────────────────────
export const jobsApi = {
  list: (limit = 50) => api.get("/jobs", { params: { limit } }),
  get: (jobId: string) => api.get(`/jobs/${jobId}`),
  create: (vendor_config_id: string, store_id: string) =>
    api.post("/jobs", { vendor_config_id, store_id }),
  retry: (jobId: string) => api.post(`/jobs/${jobId}/retry`),
  stop: (jobId: string) => api.post(`/jobs/${jobId}/stop`),
  summary: () => api.get("/jobs/summary/dashboard"),
};

// ── Billing ───────────────────────────────────────────────────────────────
export const billingApi = {
  checkout: (plan: string) => api.post(`/billing/checkout/${plan}`),
  portal: () => api.post("/billing/portal"),
};

// ── WebSocket URL builder ─────────────────────────────────────────────────
export function buildWsUrl(jobId: string, token: string, fromLine = 0): string {
  const wsBase = BASE_URL.replace(/^http/, "ws");
  return `${wsBase}/jobs/${jobId}/logs/ws?token=${token}&from_line=${fromLine}`;
}

export default api;
