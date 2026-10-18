"use client";

import { useEffect } from "react";
import { errorMessage } from "@/lib/api";
import PageMessage from "@/components/PageMessage";
import StatusBar from "@/components/StatusBar";

/** Catches a render error in the page; the root layout and its providers stay mounted. */
export default function Error({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <>
      <StatusBar state="idle" updatedAt={0} />
      <PageMessage
        title="The dashboard stopped working."
        actions={
          <button type="button" onClick={() => retry()}>
            Try again
          </button>
        }
      >
        <p>{errorMessage(error)}</p>
        <p>Try again. If this page comes back, reload the browser tab.</p>
      </PageMessage>
    </>
  );
}
