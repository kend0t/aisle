import type { Outcome } from "@/lib/api";
import { OUTCOME_LABEL } from "@/lib/format";
import styles from "./OutcomeBadge.module.css";

/** Outcome label with its color dot. Sizes with the surrounding text. */
export default function OutcomeBadge({ outcome }: { outcome: Outcome }) {
  return <span className={`${styles.badge} ${styles[outcome]}`}>{OUTCOME_LABEL[outcome]}</span>;
}
