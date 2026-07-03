import { API_BASE_URL } from "./config";
import type { ConfirmAgeRequest } from "./types";

export async function confirmAge(jobId: string, body: ConfirmAgeRequest): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/servers/${encodeURIComponent(jobId)}/confirm-age`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error((detail as { detail?: string }).detail ?? `request failed (${response.status})`);
  }
}

export async function markDead(jobId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/servers/${encodeURIComponent(jobId)}/mark-dead`, {
    method: "POST",
  });

  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error((detail as { detail?: string }).detail ?? `request failed (${response.status})`);
  }
}
