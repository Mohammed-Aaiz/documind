import { Fragment } from 'react';

/** A deliberately small, safe Markdown view. React escapes all source text. */
function inline(text: string) {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={index}>{part.slice(2, -2)}</strong>;
    if (part.startsWith('`') && part.endsWith('`')) return <code key={index}>{part.slice(1, -1)}</code>;
    return <Fragment key={index}>{part}</Fragment>;
  });
}

export function AnswerContent({ text }: { text: string }) {
  const segments = text.split(/(```text[ \t]*\r?\n[\s\S]*?(?:```|$))/g);
  return <div className="dm-answer-content">{segments.flatMap((segment, index) => {
    if (segment.startsWith('```text')) {
      const diagram = segment.replace(/^```text[ \t]*\r?\n/, '').replace(/\r?\n?```$/, '');
      return <figure className="dm-answer-diagram" key={`diagram-${index}`} aria-label="Text diagram">
        <pre><code>{diagram}</code></pre>
      </figure>;
    }

    const blocks = segment.split(/\n\s*\n/);
    return blocks.map((block, blockIndex) => {
    const lines = block.trim().split('\n');
    if (!block.trim()) return null;
    const key = `${index}-${blockIndex}`;
    if (lines.every((line) => /^\s*[-*]\s/.test(line))) return <ul key={key}>{lines.map((line, item) => <li key={item}>{inline(line.replace(/^\s*[-*]\s+/, ''))}</li>)}</ul>;
    if (lines.every((line) => /^\s*\d+[.)]\s/.test(line))) return <ol key={key}>{lines.map((line, item) => <li key={item}>{inline(line.replace(/^\s*\d+[.)]\s+/, ''))}</li>)}</ol>;
    return <div key={key}>{lines.map((line, row) => {
      if (/^#{1,4}\s/.test(line)) return <h3 key={row}>{inline(line.replace(/^#{1,4}\s+/, ''))}</h3>;
      return <Fragment key={row}>{inline(line)}{row < lines.length - 1 && <br />}</Fragment>;
    })}</div>;
    });
  })}</div>;
}
