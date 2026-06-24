"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { createInbox, listMessages, getMessage, deleteInbox, Inbox, MessageSummary, MessageDetail } from "@/lib/api";

const POLL_INTERVAL_MS = 5000;
const STORAGE_KEY = "tempmail:current_address";

export default function HomePage() {
  const [inbox, setInbox] = useState<Inbox | null>(null);
  const [messages, setMessages] = useState<MessageSummary[]>([]);
  const [selected, setSelected] = useState<MessageDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [timeLeft, setTimeLeft] = useState<string>("");
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  // ---- Auto-load inbox from localStorage on mount ----
  useEffect(() => {
    const saved = typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
    if (saved) {
      // Will re-fetch via create endpoint to extend expiry
      createInbox()
        .then((inb) => {
          setInbox(inb);
          localStorage.setItem(STORAGE_KEY, inb.address);
        })
        .catch(() => {
          // If API fails, just show empty state
        });
    }
  }, []);

  // ---- Countdown timer ----
  useEffect(() => {
    if (!inbox) return;
    const tick = () => {
      const expiryMs = inbox.expires_at.endsWith("Z")
        ? new Date(inbox.expires_at).getTime()
        : new Date(`${inbox.expires_at}Z`).getTime();
      const ms = expiryMs - Date.now();
      if (ms <= 0) {
        setTimeLeft("expired");
        return;
      }
      const mins = Math.floor(ms / 60000);
      const secs = Math.floor((ms % 60000) / 1000);
      setTimeLeft(`${mins}m ${secs}s`);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [inbox]);

  // ---- Polling for new messages ----
  const refresh = useCallback(async () => {
    if (!inbox) return;
    try {
      const msgs = await listMessages(inbox.address);
      setMessages(msgs);
    } catch (e) {
      // Silent fail on poll
    }
  }, [inbox]);

  useEffect(() => {
    if (!inbox) return;
    refresh();
    pollRef.current = setInterval(refresh, POLL_INTERVAL_MS);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [inbox, refresh]);

  // ---- Handlers ----
  const handleGenerate = async () => {
    setLoading(true);
    try {
      const inb = await createInbox();
      setInbox(inb);
      setMessages([]);
      setSelected(null);
      localStorage.setItem(STORAGE_KEY, inb.address);
      showToast("New inbox created");
    } catch (e) {
      showToast("Failed to create inbox");
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (!inbox) return;
    navigator.clipboard.writeText(inbox.address);
    showToast("Copied to clipboard");
  };

  const handleDelete = async () => {
    if (!inbox) return;
    if (!confirm("Delete this inbox? All messages will be lost.")) return;
    try {
      await deleteInbox(inbox.address);
      setInbox(null);
      setMessages([]);
      setSelected(null);
      localStorage.removeItem(STORAGE_KEY);
      showToast("Inbox deleted");
    } catch {
      showToast("Failed to delete");
    }
  };

  const handleSelectMessage = async (id: number) => {
    if (!inbox) return;
    try {
      const detail = await getMessage(inbox.address, id);
      setSelected(detail);
      // Mark as read in list
      setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, read: true } : m)));
    } catch {
      showToast("Failed to load message");
    }
  };

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2000);
  };

  // ---- Render ----
  return (
    <main className="container">
      <header className="header">
        <h1>📬 kstarid.cloud</h1>
        <p>Temporary email that auto-expires. No signup, no tracking.</p>
      </header>

      {!inbox ? (
        <div className="card" style={{ textAlign: "center" }}>
          <button onClick={handleGenerate} disabled={loading}>
            {loading ? "Generating..." : "Generate New Email"}
          </button>
          <div className="how-to-use">
            <strong>How it works:</strong>
            <ol style={{ marginLeft: "20px", marginTop: "8px" }}>
              <li>Click <strong>Generate</strong> to get a random email address</li>
              <li>Use it anywhere — signups, downloads, free trials</li>
              <li>Incoming emails appear here automatically (refreshes every 5s)</li>
              <li>The inbox expires after <strong>1 hour</strong></li>
            </ol>
          </div>
        </div>
      ) : (
        <>
          <div className="card">
            <div className="address-display">
              <span className="email">{inbox.address}</span>
              <button onClick={handleCopy}>📋 Copy</button>
            </div>
            <div className="status-bar">
              <span>⏱ Expires in: <strong>{timeLeft}</strong></span>
              <span>
                <span className="spinner"></span> Auto-refresh every 5s
              </span>
            </div>
            <div className="actions">
              <button className="secondary" onClick={handleGenerate}>🔄 New Inbox</button>
              <button className="danger" onClick={handleDelete}>🗑️ Delete</button>
            </div>
          </div>

          <div className="card">
            <h2 style={{ marginBottom: "16px", fontSize: "20px" }}>
              📥 Inbox ({messages.length})
            </h2>
            {messages.length === 0 ? (
              <div className="empty">
                <div className="icon">📭</div>
                <p>No messages yet. Send an email to your address above.</p>
              </div>
            ) : (
              <ul className="message-list">
                {messages.map((m) => (
                  <li
                    key={m.id}
                    className={`message-item ${!m.read ? "unread" : ""}`}
                    onClick={() => handleSelectMessage(m.id)}
                  >
                    <div className="from">{m.from_address || "(unknown sender)"}</div>
                    <div className="subject">{m.subject || "(no subject)"}</div>
                    <div className="time">{new Date(m.received_at).toLocaleString()}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {selected && (
            <div className="card">
              <div className="actions" style={{ marginBottom: "16px" }}>
                <button className="secondary" onClick={() => setSelected(null)}>← Back to list</button>
              </div>
              <h3 style={{ marginBottom: "8px" }}>{selected.subject || "(no subject)"}</h3>
              <div className="status-bar" style={{ marginBottom: "16px" }}>
                <span><strong>From:</strong> {selected.from_address}</span>
                <span>{new Date(selected.received_at).toLocaleString()}</span>
              </div>
              <div className="message-detail">
                {selected.body_text || "(empty)"}
              </div>
            </div>
          )}
        </>
      )}

      {toast && <div className="toast">{toast}</div>}
    </main>
  );
}
