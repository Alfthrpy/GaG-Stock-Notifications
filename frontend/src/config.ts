const apiBase = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8010";

export const API_BASE_URL = apiBase.replace(/\/$/, "");
export const WS_URL = `${API_BASE_URL.replace(/^http/, "ws")}/ws/servers`;
