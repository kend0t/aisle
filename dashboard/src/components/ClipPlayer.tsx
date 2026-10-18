"use client";

import { useState } from "react";
import { clipUrl } from "@/lib/api";
import styles from "./ClipPlayer.module.css";

type State = "loading" | "ready" | "failed";

/** The clip video with loading and error states. Mount with key={eventId} to reset per clip. */
export default function ClipPlayer({ eventId }: { eventId: string }) {
  const [state, setState] = useState<State>("loading");
  // Bumped by "Try again" to remount the video and request the clip again.
  const [attempt, setAttempt] = useState(0);

  return (
    <div className={styles.player} aria-busy={state === "loading"}>
      <video
        key={attempt}
        className={styles.video}
        src={clipUrl(eventId)}
        controls
        preload="metadata"
        playsInline
        onLoadStart={() => setState("loading")}
        // Buffering during playback is left to the native control's spinner.
        onLoadedMetadata={() => setState("ready")}
        onError={() => setState("failed")}
      />

      {state === "loading" && (
        <p className={styles.overlay} role="status">
          Loading clip
        </p>
      )}

      {state === "failed" && (
        <div className={styles.overlay} role="alert">
          <p>Clip did not load. The video file may be missing from storage.</p>
          <button
            type="button"
            onClick={() => {
              setState("loading");
              setAttempt((n) => n + 1);
            }}
          >
            Try again
          </button>
        </div>
      )}
    </div>
  );
}
