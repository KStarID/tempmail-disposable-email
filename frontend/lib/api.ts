/**
 * API client for the disposable email backend.
 *
 * BROWSER: paths are prepended with /api/backend which Next.js rewrites
 *   to http://backend:8000/api/{path}
 * SSR: paths are prepended with http://backend:8000/api/{path}
 *
 * So request paths should NOT include /api prefix.
 */

const API_PREFIX =
  typeof window === "undefined"
    ? (process.env.API_INTERNAL_URL || "http://backend:8000") + "/api"
    : "/api/backend";

export interface Inbox {
  id: number;
  address: string;
  created_at: string;
  expires_at: string;
}

export interface MessageSummary {
  id: number;
  from_address: string;
  from_name: string | null;
  subject: string;
  received_at: string;
  read: boolean;
}

export interface MessageDetail extends MessageSummary {
  inbox_id: number;
  body_text: string;
  body_html: string;
}

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const url = `${API_PREFIX}${path}`;
  const res = await fetch(url, {
    ...opts,
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`API ${res.status} (${url}): ${err}`);
  }
  return res.json();
}

export async function createInbox(): Promise<Inbox> {
  return request<Inbox>("/inbox/create", { method: "POST" });
}

export async function getInbox(address: string): Promise<Inbox> {
  return request<Inbox>(`/inbox/${encodeURIComponent(address)}`);
}

export async function listMessages(address: string): Promise<MessageSummary[]> {
  return request<MessageSummary[]>(`/inbox/${encodeURIComponent(address)}/messages`);
}

export async function getMessage(address: string, id: number): Promise<MessageDetail> {
  return request<MessageDetail>(`/inbox/${encodeURIComponent(address)}/messages/${id}`);
}

export async function deleteInbox(address: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/inbox/${encodeURIComponent(address)}`, { method: "DELETE" });
}
