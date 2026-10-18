import styles from "./Wordmark.module.css";

/** "AIsle" with the I drawn as the yellow aisle from the favicon. */
export default function Wordmark() {
  return (
    <span className={styles.wordmark}>
      <span className="visually-hidden">AIsle</span>
      <span aria-hidden="true">
        A<span className={styles.aisle} />
        sle
      </span>
    </span>
  );
}
