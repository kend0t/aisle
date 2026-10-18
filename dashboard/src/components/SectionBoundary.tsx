"use client";

import { catchError, type ErrorInfo } from "next/error";
import { errorMessage } from "@/lib/api";
import styles from "./SectionBoundary.module.css";

/** Keeps a render error in one section from blanking the rest of the page. */
function SectionFallback({ name }: { name: string }, { error, reset }: ErrorInfo) {
  return (
    <section className={styles.failed} role="alert">
      <h2>{name} did not render.</h2>
      <p>{errorMessage(error)}</p>
      {/* reset, not retry: the data lives in the query cache, so there is nothing to re-fetch. */}
      <button type="button" onClick={() => reset()}>
        Try again
      </button>
    </section>
  );
}

export default catchError(SectionFallback);
