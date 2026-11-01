import { useEffect, useRef, useState } from 'react';
import type { ChatMessage } from '../../types';
import { VoiceSpeakerButton } from '../../components/common/VoiceSpeakerButton';
import { Icon } from './WorkspaceSidebar';
import { AnswerContent } from './AnswerContent';
import { answerForReading } from './answerPresentation';

function AnswerCard({ message, onPlaybackChange, voiceActive }: { message: ChatMessage; onPlaybackChange?: (playing: boolean) => void; voiceActive?: boolean }) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  const readingText = message.sender === 'oracle'
    ? answerForReading(message.text, message.sources?.length || 0) : message.text;
  const documentCount = new Set(message.sources?.map((source) => source.documentId || source.documentName)).size;
  return <article className={`dm-message ${message.sender === 'user' ? 'is-user' : 'is-answer'}`}>
    <div className="dm-message-author"><span className="dm-answer-avatar"><Icon name={message.sender === 'user' ? 'person' : 'auto_awesome'} /></span><strong>{message.sender === 'user' ? 'You' : 'DocuMind'}</strong>{message.marks ? <span className="dm-tag">{message.marks} marks</span> : null}{message.streaming && <span className="dm-tag">Draft · checking when complete</span>}</div>
    <div className="dm-message-text">{message.text ? message.sender === 'oracle' && !message.streaming ? <AnswerContent text={readingText} /> : readingText : (message.streaming ? <span className="dm-thinking">Finding evidence and preparing your answer…</span> : 'The available evidence was insufficient to answer this question.')}</div>
    {!!message.warnings?.length && <details className="dm-evidence dm-answer-notes"><summary><Icon name="info" />Answer notes<Icon name="expand_more" /></summary><div>{message.warnings.map((warning, index) => <p className="dm-answer-warning" key={index}>{warning}</p>)}</div></details>}
    {!!message.sources?.length && <details className="dm-evidence"><summary><Icon name="menu_book" />Sources · {documentCount} {documentCount === 1 ? 'document' : 'documents'}<Icon name="expand_more" /></summary><div>{message.sources.map((source, index) => <article key={`${source.chunkId}-${index}`}><strong><span>Passage {index + 1}</span> · {source.documentName}</strong><small>{source.page != null ? `Page ${source.page}` : 'Page not recorded'}{source.section ? ` · ${source.section}` : ''}{source.retrievalPath ? ` · ${source.retrievalPath}` : ''}</small>{source.knowledgeGraphPath && <section className="dm-kg-evidence" aria-label="Entity relation evidence"><strong>Graph path{source.knowledgeGraphHops != null ? ` · ${source.knowledgeGraphHops} hops` : ''}</strong><p>{source.knowledgeGraphPath}</p>{source.knowledgeGraphPredicate && <small>Relation: {source.knowledgeGraphPredicate}</small>}{source.knowledgeGraphQuote && <blockquote>{source.knowledgeGraphQuote}</blockquote>}</section>}<p>{source.content}</p></article>)}</div></details>}
    {message.sender === 'oracle' && !message.streaming && message.text && <div className="dm-message-actions">
      <button className="dm-text-button" onClick={async () => { try { await navigator.clipboard.writeText(readingText); setCopied(true); setCopyError(false); } catch { setCopyError(true); } }}><Icon name="content_copy" />{copied ? 'Copied' : 'Copy'}</button>
      <VoiceSpeakerButton text={readingText} onPlaybackChange={onPlaybackChange} disabled={voiceActive} />
      <small>{message.model || message.engine || ''}{message.latencyMs != null ? ` · ${(message.latencyMs / 1000).toFixed(1)}s` : ''}</small>
      {copyError && <span role="status">Clipboard is unavailable.</span>}
    </div>}
  </article>;
}

export function AnswerThread({ messages, onPlaybackChange, voiceActive }: { messages: ChatMessage[]; onPlaybackChange?: (playing: boolean) => void; voiceActive?: boolean }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [messages]);
  return <div className="dm-thread" aria-label="Conversation">{messages.map((message) => <AnswerCard key={message.id} message={message} onPlaybackChange={onPlaybackChange} voiceActive={voiceActive} />)}<div ref={end} /></div>;
}
