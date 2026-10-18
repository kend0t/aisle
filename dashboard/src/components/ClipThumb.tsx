"use client";

import { useState } from "react";
import { thumbnailUrl } from "@/lib/api";
import styles from "./ClipThumb.module.css";

interface Props {
  eventId: string;
  size: "s" | "m";
  onOpen: (eventId: string) => void;
}

export default function ClipThumb({ eventId, size, onOpen }: Props) {
  const [failed, setFailed] = useState(false);

  return (
    <button
      type="button"
      className={`${styles.thumb} ${styles[size]}`}
      onClick={() => onOpen(eventId)}
      aria-label={`Play clip ${eventId}`}
      title={`Play clip ${eventId}`}
    >
      {!failed && (
        // eslint-disable-next-line @next/next/no-img-element -- served by the backend, not the Next image pipeline
        <img
          src={thumbnailUrl(eventId)}
          alt=""
          loading="lazy"
          decoding="async"
          onError={() => setFailed(true)}
        />
      )}
      <span className={styles.play} aria-hidden="true" />
    </button>
  );
}
