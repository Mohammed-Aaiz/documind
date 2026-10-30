import React, { useEffect, useState } from 'react';
import type { Page, WorkspaceTask } from '../types';
import { useWorkspace } from '../context/WorkspaceContext';
import { apiConversationStatus, ApiConversationStatus } from '../lib/api';
import { VoiceStreamButton } from '../components/common/VoiceStreamButton';
import { stopActiveTtsPlayback } from '../components/common/VoiceSpeakerButton';
import { WORKSPACES } from '../features/workspace/config';
import { SourceLibrary } from '../features/workspace/SourceLibrary';
import { AnswerThread } from '../features/workspace/AnswerThread';
import { Icon } from '../features/workspace/WorkspaceSidebar';

export const WorkspacePage: React.FC<{ onNavigate: (page: Page) => void }> = () => {
  const context = useWorkspace();
  const { workspace = 'student', files, messages, chatInput, setChatInput, answerFormat = '10', setAnswerFormat,
    sendMessage, isSending, cancelMessage, chatError, activeSessionId, applyVoiceAnswer, task = 'answer', setTask, sessionsLoading, startNewConversation } = context;
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [ttsPlaying, setTtsPlaying] = useState(false);
  const [voiceActive, setVoiceActive] = useState(false);
  const [provider, setProvider] = useState<ApiConversationStatus | null>(null);
  const [providerError, setProviderError] = useState(false);
  const config = WORKSPACES[workspace];
  useEffect(() => {
    let active = true;
    if (context.workspace) apiConversationStatus().then((status) => { if (active) { setProvider(status); setProviderError(false); } }).catch(() => { if (active) setProviderError(true); });
    return () => { active = false; };
  }, [context.workspace]);
  useEffect(() => { setTtsPlaying(false); return () => stopActiveTtsPlayback({ announceStop: false }); }, [workspace, activeSessionId]);
  const model = provider?.conversationModel;
  const providerName = provider?.provider ?? model?.provider;
  const hosted = provider?.hosted ?? model?.hosted ?? providerName === 'groq';
  const readyCount = files.filter((file) => file.status === 'ready' || file.status === 'partial').length;
  function exportChat() {
    const text = `# DocuMind · ${config.label}\n\n` + messages.filter((message) => !message.streaming).map((message) => `## ${message.sender === 'user' ? 'You' : 'DocuMind'}\n\n${message.text}\n\n${message.sources?.map((source, index) => `[${index + 1}] ${source.documentName}${source.page != null ? `, page ${source.page}` : ''}\n${source.content}`).join('\n\n') ?? ''}`).join('\n\n');
    const url = URL.createObjectURL(new Blob([text], { type: 'text/markdown' }));
    const link = document.createElement('a'); link.href = url; link.download = `documind-${workspace}-chat.md`; link.click(); URL.revokeObjectURL(url);
  }
  return <div className={`dm-workspace ${libraryOpen ? 'library-open' : ''}`}>
    <section className="dm-conversation">
      <div className="dm-workspace-toolbar"><div><span className="dm-space-pill"><Icon name={config.icon} />{config.label} workspace</span><span className="dm-private-note"><Icon name="lock" />Separate chat history</span></div><div><button className="dm-icon-button" disabled={!messages.length || isSending} aria-label="Export conversation as Markdown" onClick={exportChat}><Icon name="download" /></button><button className="dm-button dm-library-toggle" onClick={() => setLibraryOpen(!libraryOpen)} aria-expanded={libraryOpen}><Icon name="folder_open" />Sources<span>{files.length}</span></button></div></div>
      <div className="dm-conversation-body" key={`${workspace}-${activeSessionId ?? 'home'}`}>
        {messages.length ? <AnswerThread messages={messages} onPlaybackChange={setTtsPlaying} voiceActive={voiceActive} /> : <div className="dm-welcome">
          <div className="dm-welcome-emblem"><Icon name={config.icon} /><span /></div>
          <p className="dm-eyebrow">{config.eyebrow}</p><h1>{config.title}</h1><p className="dm-welcome-description">{config.description}</p>
          <div className="dm-starters">{config.actions.map((action) => <button key={action.task} onClick={() => { setTask(action.task); setChatInput(action.prompt); document.getElementById('workspace-question')?.focus(); }}><span className="dm-starter-icon"><Icon name={action.icon} /></span><strong>{action.title}</strong><small>{action.description}</small><Icon name="north_east" className="dm-starter-arrow" /></button>)}</div>
          <div className="dm-welcome-footnote"><Icon name="format_quote" />Built around your sources. Designed for your thinking.</div>
        </div>}
      </div>
      <div className="dm-composer-area">
        {chatError && <div className="dm-alert" role="alert"><Icon name="error" /><span>{chatError}</span></div>}
        {hosted && <p className="dm-hosted-note"><Icon name="cloud" />Groq hosted inference · your question and relevant source passages are sent to Groq.</p>}
        <form className="dm-composer" onSubmit={(event) => { event.preventDefault(); if (!voiceActive) void sendMessage(); }}>
          <label className="sr-only" htmlFor="workspace-question">Ask your documents</label>
          <textarea id="workspace-question" rows={2} maxLength={2000} value={chatInput} onChange={(event) => setChatInput(event.target.value)} placeholder={workspace === 'student' ? 'What would you like to understand?' : 'What would you like to investigate?'} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); if (!isSending && !voiceActive) void sendMessage(); } }} />
          <div className="dm-composer-controls"><div className="dm-format-controls">
            {workspace === 'student' ? <div className="dm-mark-selector" aria-label="Answer depth">{(['5', '10', '15'] as const).map((mark) => <button type="button" key={mark} aria-pressed={answerFormat === mark} onClick={() => setAnswerFormat(mark)}>{mark}<span> marks</span></button>)}</div> : <label className="dm-task-select"><span className="sr-only">Research task</span><select value={task} onChange={(event) => setTask(event.target.value as WorkspaceTask)}>{config.actions.map((action) => <option key={action.task} value={action.task}>{action.title}</option>)}</select></label>}
            <span className="dm-source-count"><Icon name="description" />{readyCount} searchable</span>
          </div><div className="dm-compose-actions">
            {activeSessionId ? <VoiceStreamButton key={`${workspace}-${activeSessionId}`} sessionId={activeSessionId} answerFormat={answerFormat} workspace={workspace} task={task} onAnswer={applyVoiceAnswer} onActiveChange={setVoiceActive} disabled={isSending || ttsPlaying} /> : <button className="dm-icon-button" type="button" title="Start a chat to talk with your documents" aria-label="Start a voice conversation" onClick={() => void startNewConversation()}><Icon name="graphic_eq" /></button>}
            {isSending ? <button className="dm-send" type="button" aria-label="Stop generating" onClick={cancelMessage}><Icon name="stop" /></button> : <button className="dm-send" type="submit" aria-label="Send question" disabled={!chatInput.trim() || sessionsLoading || voiceActive}><Icon name="arrow_upward" /></button>}
          </div></div>
        </form>
        <div className="dm-composer-caption"><span>{providerError ? 'Provider status unavailable' : providerName ? `${providerName === 'ollama' ? 'Local · Ollama' : providerName}${(provider?.available ?? model?.available) === false ? ' · unavailable' : ''}` : 'Checking answer provider…'}</span><span>Review citations. AI answers can be incomplete.</span><span>Enter to send</span></div>
      </div>
    </section>
    <SourceLibrary />
  </div>;
};
