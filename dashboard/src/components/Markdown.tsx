import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import styles from "./Markdown.module.css";

/*
  Renders Copilot answers: GitHub-flavored markdown (tables included). Event IDs
  (evt_...) become buttons that open the clip.
*/

const CLIP_HREF = "#clip-";
const EVENT_ID = /`?\b(evt_[a-zA-Z0-9]+)\b`?/g;

interface Props {
  content: string;
  onOpenClip?: (eventId: string) => void;
}

export default function Markdown({ content, onOpenClip }: Props) {
  const heading: Components["h1"] = ({ children }) => <p className={styles.heading}>{children}</p>;

  const components: Components = {
    h1: heading,
    h2: heading,
    h3: heading,
    h4: heading,
    table: ({ children }) => (
      <div className={styles.tableWrap}>
        <table>{children}</table>
      </div>
    ),
    a: ({ href, children }) => {
      if (href?.startsWith(CLIP_HREF) && onOpenClip) {
        const eventId = href.slice(CLIP_HREF.length);
        return (
          <button type="button" className={styles.clipLink} onClick={() => onOpenClip(eventId)}>
            {children}
          </button>
        );
      }
      return (
        <a href={href} target="_blank" rel="noreferrer">
          {children}
        </a>
      );
    },
  };

  // Turn each event ID, bare or in backticks, into a link the `a` renderer above recognizes.
  const linked = onOpenClip ? content.replace(EVENT_ID, `[$1](${CLIP_HREF}$1)`) : content;

  return (
    <div className={styles.markdown}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {linked}
      </ReactMarkdown>
    </div>
  );
}
