import type { ReactNode } from "react";
import styles from "./Markdown.module.css";

/*
  Renders the small markdown subset Copilot returns: headings, paragraphs,
  bullet and numbered lists, tables, bold, italic, and code. Event IDs
  (evt_...) become buttons that open the clip.
*/

const EVENT_ID = /^evt_[a-zA-Z0-9]+$/;
const TABLE_SEPARATOR = /^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$/;

interface Props {
  content: string;
  onOpenClip?: (eventId: string) => void;
}

function splitRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

export default function Markdown({ content, onOpenClip }: Props) {
  const inline = (text: string, keyPrefix: string): ReactNode[] =>
    text.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*|\bevt_[a-zA-Z0-9]+\b)/g).map((part, i) => {
      const key = `${keyPrefix}-${i}`;
      const bare = part.replace(/^`|`$/g, "");
      if (EVENT_ID.test(bare) && onOpenClip) {
        return (
          <button key={key} type="button" className={styles.clipLink} onClick={() => onOpenClip(bare)}>
            {bare}
          </button>
        );
      }
      if (part.startsWith("**") && part.endsWith("**")) return <strong key={key}>{part.slice(2, -2)}</strong>;
      if (part.startsWith("`") && part.endsWith("`")) return <code key={key}>{bare}</code>;
      if (part.length > 2 && part.startsWith("*") && part.endsWith("*")) return <em key={key}>{part.slice(1, -1)}</em>;
      return part;
    });

  const lines = content.split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i].trim();

    if (!line) {
      i++;
      continue;
    }

    const heading = line.match(/^(#{1,4})\s+(.*)$/);
    if (heading) {
      blocks.push(
        <p key={i} className={styles.heading}>
          {inline(heading[2], `h${i}`)}
        </p>,
      );
      i++;
      continue;
    }

    if (line.startsWith("|") && i + 1 < lines.length && TABLE_SEPARATOR.test(lines[i + 1].trim())) {
      const header = splitRow(line);
      const rows: string[][] = [];
      i += 2;
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        rows.push(splitRow(lines[i]));
        i++;
      }
      blocks.push(
        <div key={`t${i}`} className={styles.tableWrap}>
          <table>
            <thead>
              <tr>
                {header.map((cell, c) => (
                  <th key={c}>{inline(cell, `th${i}-${c}`)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, r) => (
                <tr key={r}>
                  {row.map((cell, c) => (
                    <td key={c}>{inline(cell, `td${i}-${r}-${c}`)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }

    const listMatch = /^([-*]|\d+\.)\s+/;
    if (listMatch.test(line)) {
      const ordered = /^\d+\./.test(line);
      const items: string[] = [];
      while (i < lines.length && listMatch.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(listMatch, ""));
        i++;
      }
      const ListTag = ordered ? "ol" : "ul";
      blocks.push(
        <ListTag key={`l${i}`}>
          {items.map((item, n) => (
            <li key={n}>{inline(item, `li${i}-${n}`)}</li>
          ))}
        </ListTag>,
      );
      continue;
    }

    blocks.push(<p key={i}>{inline(line, `p${i}`)}</p>);
    i++;
  }

  return <div className={styles.markdown}>{blocks}</div>;
}
