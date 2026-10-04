import type { ReactNode } from "react";

/**
 * Minimal renderer for the markdown the agent actually produces: **bold**,
 * bullet lists, and paragraphs.
 *
 * Deliberately not a markdown library. This builds React elements rather than
 * setting innerHTML, so model output — which can include text copied from the
 * catalogue — can never inject markup into the page.
 */

function inline(text: string, keyPrefix: string): ReactNode[] {
  // Split on **bold**, keeping the delimited parts.
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") && part.length > 4 ? (
      <strong key={`${keyPrefix}-${i}`}>{part.slice(2, -2)}</strong>
    ) : (
      part
    ),
  );
}

export default function Markdown({ text }: { text: string }) {
  const lines = text.split("\n");
  const blocks: ReactNode[] = [];
  let bullets: string[] = [];
  let paragraph: string[] = [];

  const flushBullets = () => {
    if (!bullets.length) return;
    const items = bullets;
    blocks.push(
      <ul key={`ul-${blocks.length}`} className="md-list">
        {items.map((item, i) => (
          <li key={i}>{inline(item, `li-${blocks.length}-${i}`)}</li>
        ))}
      </ul>,
    );
    bullets = [];
  };

  const flushParagraph = () => {
    if (!paragraph.length) return;
    const body = paragraph.join(" ");
    blocks.push(<p key={`p-${blocks.length}`}>{inline(body, `p-${blocks.length}`)}</p>);
    paragraph = [];
  };

  for (const line of lines) {
    const trimmed = line.trim();
    const bullet = /^[-*•]\s+(.*)$/.exec(trimmed);
    if (bullet) {
      flushParagraph();
      bullets.push(bullet[1]);
    } else if (trimmed === "") {
      flushBullets();
      flushParagraph();
    } else {
      flushBullets();
      paragraph.push(trimmed);
    }
  }
  flushBullets();
  flushParagraph();

  return <>{blocks}</>;
}
