"use client";

import { useEffect, useRef, useState } from "react";
import { isUnreachable, type ChatTurn } from "@/lib/api";
import { useChat, useQuickPrompts } from "@/lib/queries";
import ClipThumb from "./ClipThumb";
import Markdown from "./Markdown";
import styles from "./CopilotPanel.module.css";

interface Message {
  role: "user" | "assistant" | "error";
  content: string;
  referencedEvents?: string[];
  followups?: string[];
}

interface Props {
  /** Desktop: the panel is shown. */
  expanded: boolean;
  /** Under 960 px: the bottom sheet is shown. */
  sheetOpen: boolean;
  onHide: () => void;
  onCloseSheet: () => void;
  onOpenClip: (eventId: string) => void;
}

/** Starter chips show the short title and send the full question. */
const STARTERS = 4;

function toHistory(messages: Message[]): ChatTurn[] {
  return messages
    .filter((m): m is Message & { role: "user" | "assistant" } => m.role !== "error")
    .slice(-6)
    .map(({ role, content }) => ({ role, content }));
}

export default function CopilotPanel({ expanded, sheetOpen, onHide, onCloseSheet, onOpenClip }: Props) {
  const quickPrompts = useQuickPrompts().data ?? [];
  const chat = useChat();
  const pending = chat.isPending;
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: reduce ? "auto" : "smooth",
    });
  }, [messages, pending]);

  // Focus the composer when the panel or sheet is opened, not on the first render.
  const wasVisible = useRef({ expanded, sheetOpen });
  useEffect(() => {
    const before = wasVisible.current;
    if ((expanded && !before.expanded) || (sheetOpen && !before.sheetOpen)) {
      inputRef.current?.focus();
    }
    wasVisible.current = { expanded, sheetOpen };
  }, [expanded, sheetOpen]);

  const send = (text: string, history: ChatTurn[]) => {
    chat.mutate(
      { message: text, history },
      {
        onSuccess: (reply) =>
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              content: reply.response,
              referencedEvents: reply.referenced_events,
              followups: reply.suggested_followups,
            },
          ]),
        onError: (err) =>
          setMessages((prev) => [
            ...prev,
            {
              role: "error",
              content: isUnreachable(err)
                ? "Copilot is offline. Check that the backend is running, then try again."
                : `No answer: ${err.message}`,
            },
          ]),
      },
    );
  };

  const ask = (question: string) => {
    const text = question.trim();
    if (!text || pending) return;
    const history = toHistory(messages);
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    send(text, history);
  };

  /** Drops the error and sends the last question again. */
  const retry = () => {
    const withoutError = messages.slice(0, -1);
    const lastQuestion = withoutError.at(-1);
    if (!lastQuestion || lastQuestion.role !== "user" || pending) return;
    setMessages(withoutError);
    send(lastQuestion.content, toHistory(withoutError.slice(0, -1)));
  };

  const canSend = input.trim().length > 0 && !pending;

  return (
    <aside
      className={`${styles.panel} ${expanded ? "" : styles.collapsed} ${sheetOpen ? styles.open : ""}`}
      aria-labelledby="copilot-heading"
      onKeyDown={(e) => {
        if (e.key === "Escape" && sheetOpen) onCloseSheet();
      }}
    >
      <div className={styles.header}>
        <h2 id="copilot-heading">Ask about this shelf</h2>
        <div className={styles.headerActions}>
          {messages.length > 0 && (
            <button type="button" onClick={() => setMessages([])}>
              New chat
            </button>
          )}
          <button type="button" className={styles.hideButton} onClick={onHide}>
            Hide
          </button>
          <button type="button" className={styles.closeButton} onClick={onCloseSheet}>
            Close
          </button>
        </div>
      </div>

      <div className={styles.body} ref={scrollRef} aria-live="polite">
        {messages.map((message, index) => (
          <div key={index} className={`${styles.message} ${styles[message.role]}`}>
            {message.role === "assistant" ? (
              <Markdown content={message.content} onOpenClip={onOpenClip} />
            ) : (
              <p>{message.content}</p>
            )}

            {message.role === "error" && index === messages.length - 1 && (
              <button type="button" className={styles.retry} onClick={retry} disabled={pending}>
                Try again
              </button>
            )}

            {message.referencedEvents && message.referencedEvents.length > 0 && (
              <div className={styles.cited}>
                {message.referencedEvents.map((id) => (
                  <ClipThumb key={id} eventId={id} size="s" onOpen={onOpenClip} />
                ))}
              </div>
            )}

            {message.followups && message.followups.length > 0 && index === messages.length - 1 && (
              <div className={styles.chips}>
                {message.followups.map((f) => (
                  <button key={f} type="button" onClick={() => ask(f)} disabled={pending}>
                    {f}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}

        {pending && (
          <div className={styles.typing} role="status" aria-label="Copilot is answering">
            <span />
            <span />
            <span />
          </div>
        )}
      </div>

      <div className={styles.footer}>
        {messages.length === 0 && (
          <>
            <p className={styles.empty}>
              Gemini answers from the clips on this page and links every clip it cites.
            </p>
            {quickPrompts.length > 0 && (
              <div className={styles.chips}>
                {quickPrompts.slice(0, STARTERS).map((qp) => (
                  <button key={qp.id} type="button" title={qp.prompt} onClick={() => ask(qp.prompt)}>
                    {qp.title}
                  </button>
                ))}
              </div>
            )}
          </>
        )}

        <form
          className={styles.composer}
          onSubmit={(e) => {
            e.preventDefault();
            ask(input);
          }}
        >
          <label htmlFor="copilot-input" className="visually-hidden">
            Question
          </label>
          <textarea
            id="copilot-input"
            ref={inputRef}
            rows={1}
            value={input}
            placeholder="Ask about these clips"
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                ask(input);
              }
            }}
          />
          <button type="submit" className={styles.send} disabled={!canSend} aria-label="Send">
            <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true">
              <path
                d="M10 16V4M4.5 9.5 10 4l5.5 5.5"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </form>
      </div>
    </aside>
  );
}
