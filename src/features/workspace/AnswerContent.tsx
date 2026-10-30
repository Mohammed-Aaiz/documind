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
  const blocks = text.split(/\n\s*\n/);
  return <div className="dm-answer-content">{blocks.map((block, index) => {
    const lines = block.trim().split('\n');
    if (lines.every((line) => /^\s*[-*]\s/.test(line))) return <ul key={index}>{lines.map((line, item) => <li key={item}>{inline(line.replace(/^\s*[-*]\s+/, ''))}</li>)}</ul>;
    if (lines.every((line) => /^\s*\d+[.)]\s/.test(line))) return <ol key={index}>{lines.map((line, item) => <li key={item}>{inline(line.replace(/^\s*\d+[.)]\s+/, ''))}</li>)}</ol>;
    return <div key={index}>{lines.map((line, row) => {
      if (/^#{1,4}\s/.test(line)) return <h3 key={row}>{inline(line.replace(/^#{1,4}\s+/, ''))}</h3>;
      return <Fragment key={row}>{inline(line)}{row < lines.length - 1 && <br />}</Fragment>;
    })}</div>;
  })}</div>;
}
