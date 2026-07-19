import { Fragment, type ReactNode } from 'react';

function renderInline(text: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean);
  return parts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={index}>{part.slice(1, -1)}</code>;
    }
    return <Fragment key={index}>{part}</Fragment>;
  });
}

/** Small, safe subset used for model answers. It never renders raw HTML. */
export function SafeMarkdownText({ text }: { text: string }) {
  return (
    <div>
      {text.split(/\r?\n/).map((line, index) => {
        const bullet = line.match(/^\s*[-*]\s+(.+)$/);
        if (bullet) {
          return (
            <div key={index} style={{ display: 'flex', gap: 8 }}>
              <span aria-hidden="true">•</span>
              <span>{renderInline(bullet[1])}</span>
            </div>
          );
        }
        return line ? <div key={index}>{renderInline(line)}</div> : <br key={index} />;
      })}
    </div>
  );
}
