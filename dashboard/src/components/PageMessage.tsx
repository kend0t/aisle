import styles from "./PageMessage.module.css";

interface Props {
  title: string;
  children?: React.ReactNode;
  /** Buttons or links that say what to do next. */
  actions?: React.ReactNode;
}

/** Full-page message for when the dashboard cannot show data. */
export default function PageMessage({ title, children, actions }: Props) {
  return (
    <section className={styles.message} aria-live="polite">
      <h1>{title}</h1>
      {children}
      {actions && <div className={styles.actions}>{actions}</div>}
    </section>
  );
}
