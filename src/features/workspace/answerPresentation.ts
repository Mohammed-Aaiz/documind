import type { ChatMessage } from '../../types';

/** Reading/copy/export formatting only; saved answers keep their verified references. */
export function answerForReading(text: string, sourceCount: number): string {
  if (sourceCount < 1) return text;
  return text.split(/(```[\s\S]*?(?:```|$)|`[^`\n]*`)/g).map((part) => {
    if (part.startsWith('`')) return part;
    let changed = false;
    const cleaned = part.replace(/\[(\d{1,3})\](?!\()/g, (marker, number: string, offset: number) => {
      const before = part[offset - 1] || '';
      if (before === '\\' || /[\p{L}\p{N}_]/u.test(before)) return marker;
      const id = Number(number);
      if (id < 1 || id > sourceCount) return marker;
      changed = true;
      return '';
    });
    return changed ? cleaned.replace(/[ \t]+([.,;:!?])/g, '$1').replace(/[ \t]{2,}/g, ' ')
      .replace(/[ \t]+(?=\r?\n)/g, '').replace(/^#{1,6}[ \t]*$/gm, '') : part;
  }).join('');
}

export function conversationMarkdown(messages: ChatMessage[], label: string): string {
  const turns = messages.filter((message) => !message.streaming).map((message) => {
    const answer = message.sender === 'oracle';
    const body = answer ? answerForReading(message.text, message.sources?.length || 0) : message.text;
    const sources = new Set((answer ? message.sources : [])?.map((source) => {
      const name = source.documentName.replace(/[\r\n]+/g, ' ').replace(/[\\`*_<>\[\]]/g, '\\$&');
      return `- ${name}${source.page != null ? ` · Page ${source.page}` : ''}`;
    }));
    return `## ${answer ? 'DocuMind' : 'You'}\n\n${body.trim()}${sources.size ? `\n\n### Sources\n\n${[...sources].join('\n')}` : ''}`;
  });
  return `# DocuMind · ${label}\n\n${turns.join('\n\n---\n\n')}\n`;
}
