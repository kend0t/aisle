"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError, type QuickPrompt } from "@/lib/api";
import Markdown from "./Markdown";
import styles from "./CopilotPanel.module.css";

interface Message {
  role: "user" | "assistant" | "error";
  content: string;
  referencedEvents?: string[];
  followups?: string[];
}

interface Props {
  eventCount: number;
  quickPrompts: QuickPrompt[];
  open: boolean;
  onClose: () => void;
  onOpenClip: (eventId: string) => void;
}

export default function CopilotPanel({ eventCount, quickPrompts, open, onClose, onOpenClip }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, pending]);

  const ask = async (question: string) => {
    const text = question.trim();
    if (!text || pending) return;

    const history = messages
      .filter((m): m is Message & { role: "user" | "assistant" } => m.role !== "error")
      .slice(-6)
      .map(({ role, content }) => ({ role, content }));

    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setPending(true);
    try {
      const reply = await api.chat(text, history);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: reply.response,
          referencedEvents: reply.referenced_events,
          followups: reply.suggested_followups,
        },
      ]);
    } catch (err) {
      const reason = err instanceof ApiError ? err.message : "The request failed.";
      setMessages((prev) => [
        ...prev,
        { role: "error", content: `No answer. ${reason} Check that the backend is running, then ask again.` },
      ]);
    } finally {
      setPending(false);
    }
  };

  return (
    <aside
      className={`${styles.panel} ${open ? styles.open : ""}`}
      aria-labelledby="copilot-heading"
    >
      <div className={styles.header}>
        <div>
          <h2 id="copilot-heading">Ask about this shelf</h2>
          <p>
            {eventCount > 0
              ? `Gemini answers from the ${eventCount} clips on this page and cites them.`
              : "Gemini answers from the clips on this page and cites them."}
          </p>
        </div>
        <div className={styles.headerActions}>
          {messages.length > 0 && (
            <button type="button" onClick={() => setMessages([])}>
              Clear
            </button>
          )}
          <button type="button" className={styles.closeButton} onClick={onClose}>
            Close
          </button>
        </div>
      </div>

      <div className={styles.body} ref={scrollRef} aria-live="polite">
        {messages.length === 0 && quickPrompts.length > 0 && (
          <div className={styles.suggestions}>
            <p className={styles.suggestionsLabel}>Try one of these</p>
            {quickPrompts.map((qp) => (
              <button key={qp.id} type="button" onClick={() => ask(qp.prompt)}>
                <strong>{qp.title}</strong>
                <span>{qp.prompt}</span>
              </button>
            ))}
          </div>
        )}

        {messages.map((message, index) => (
          <div key={index} className={`${styles.message} ${styles[message.role]}`}>
            {message.role === "assistant" ? (
              <Markdown content={message.content} onOpenClip={onOpenClip} />
            ) : (
              <p>{message.content}</p>
            )}

            {message.referencedEvents && message.referencedEvents.length > 0 && (
              <div className={styles.cited}>
                <span>Clips cited</span>
                {message.referencedEvents.map((id) => (
                  <button key={id} type="button" onClick={() => onOpenClip(id)}>
                    {id}
                  </button>
                ))}
              </div>
            )}

            {message.followups && message.followups.length > 0 && index === messages.length - 1 && (
              <div className={styles.followups}>
                {message.followups.map((f) => (
                  <button key={f} type="button" onClick={() => ask(f)}>
                    {f}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}

        {pending && <p className={styles.pending}>Gemini is reading the clips</p>}
      </div>

      <form
        className={styles.form}
        onSubmit={(e) => {
          e.preventDefault();
          void ask(input);
        }}
      >
        <label htmlFor="copilot-input" className="visually-hidden">
          Question
        </label>
        <textarea
          id="copilot-input"
          rows={2}
          value={input}
          placeholder="Why are shoppers putting cereal back?"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void ask(input);
            }
          }}
        />
        <button type="submit" disabled={pending || !input.trim()}>
          Ask
        </button>
      </form>
    </aside>
  );
}
