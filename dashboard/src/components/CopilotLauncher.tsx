import styles from "./CopilotLauncher.module.css";

interface Props {
  /** Desktop panel is expanded: hide the launcher on wide screens. */
  expanded: boolean;
  /** Bottom sheet is open: hide the launcher on narrow screens. */
  sheetOpen: boolean;
  onOpen: () => void;
}

export default function CopilotLauncher({ expanded, sheetOpen, onOpen }: Props) {
  return (
    <button
      type="button"
      className={`${styles.launcher} ${expanded ? styles.expanded : ""} ${sheetOpen ? styles.sheetOpen : ""}`}
      onClick={onOpen}
    >
      <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true">
        <path
          d="M4 4.5h12a1.5 1.5 0 0 1 1.5 1.5v7a1.5 1.5 0 0 1-1.5 1.5H9l-4 3v-3H4A1.5 1.5 0 0 1 2.5 13V6A1.5 1.5 0 0 1 4 4.5Z"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinejoin="round"
        />
      </svg>
      Ask about this shelf
    </button>
  );
}
