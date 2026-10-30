import { useCallback, useEffect, useRef, useState } from 'react';
import { apiCreateSession, apiGetConversation, apiListSessions, apiStreamConversation, apiDeleteSession, ApiConversationAnswer, ApiConversationTurn } from '../../lib/api';
import type { ChatMessage, ChatSession, WorkspaceMode, WorkspaceTask } from '../../types';
import type { VoiceServerAnswer } from '../../lib/voiceStream';

interface ModeState {
  activeSessionId: string | null; sessions: ChatSession[]; messages: ChatMessage[]; chatInput: string;
  answerFormat: '5' | '10' | '15'; task: WorkspaceTask; busy: boolean; loading: boolean;
  error: string | null; memoryBackend: string | null;
}
const initial = (mode: WorkspaceMode): ModeState => ({ activeSessionId: null, sessions: [], messages: [], chatInput: '', answerFormat: '10',
  task: mode === 'student' ? 'answer' : 'synthesis', busy: false, loading: false, error: null, memoryBackend: null });
const fresh = () => ({ student: initial('student'), research: initial('research') });

function messagesFromHistory(turns: ApiConversationTurn[], answer?: ApiConversationAnswer | VoiceServerAnswer): ChatMessage[] {
  const last = turns.map((turn) => turn.role).lastIndexOf('assistant');
  return turns.map((turn, index) => ({ id: `turn-${index}-${turn.createdAt}`, sender: turn.role === 'user' ? 'user' : 'oracle',
    text: turn.content, timestamp: turn.createdAt,
    ...(turn.role === 'assistant' && turn.metadata ? { ...turn.metadata, engine: turn.metadata.engine as ChatMessage['engine'] } : {}),
    ...(index === last && answer ? {
      sources: answer.sources, verification: answer.verification, warnings: answer.warnings,
      engine: answer.engine as ChatMessage['engine'], model: answer.model, marks: answer.marks,
      insufficientContext: answer.insufficientContext,
      latencyMs: 'latencyMs' in answer ? answer.latencyMs : undefined,
    } : {}) }));
}

export function useWorkspaceChats(workspace: WorkspaceMode, identity: string) {
  const [states, setStates] = useState(fresh);
  const stateRef = useRef(states); stateRef.current = states;
  const modeRef = useRef(workspace); modeRef.current = workspace;
  const epoch = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const update = useCallback((mode: WorkspaceMode, patch: Partial<ModeState> | ((previous: ModeState) => Partial<ModeState>)) => {
    setStates((previous) => {
      const next = { ...previous, [mode]: { ...previous[mode], ...(typeof patch === 'function' ? patch(previous[mode]) : patch) } };
      stateRef.current = next; return next;
    });
  }, []);
  const cancelMessage = useCallback(() => {
    const previousEpoch = epoch.current;
    epoch.current++; controller.current?.abort(); controller.current = null;
    update(modeRef.current, (state) => ({ busy: false, loading: false,
      chatInput: state.busy ? state.messages.find((message) => message.id === `user-${previousEpoch}`)?.text ?? state.chatInput : state.chatInput,
      messages: state.messages.filter((message) => !message.streaming && message.id !== `user-${previousEpoch}`) }));
  }, [update]);
  const refreshSessions = useCallback(async (mode = modeRef.current) => {
    const requestEpoch = epoch.current;
    update(mode, { loading: true });
    try {
      const sessions = await apiListSessions(mode);
      if (requestEpoch === epoch.current) update(mode, { sessions: sessions.filter((session) => (session.workspace ?? 'student') === mode), error: null });
    } catch (error) { if (requestEpoch === epoch.current) update(mode, { error: error instanceof Error ? error.message : 'Could not load chats.' }); }
    finally { if (requestEpoch === epoch.current) update(mode, { loading: false }); }
  }, [update]);
  useEffect(() => {
    epoch.current++; controller.current?.abort(); setStates(fresh());
    return () => { epoch.current++; controller.current?.abort(); };
  }, [identity]);
  useEffect(() => { if (identity) void refreshSessions(workspace); }, [workspace, identity, refreshSessions]);

  const startNewConversation = useCallback(async () => {
    cancelMessage(); const mode = modeRef.current; const requestEpoch = epoch.current;
    update(mode, { loading: true, error: null });
    try {
      const session = await apiCreateSession(mode);
      if (requestEpoch !== epoch.current) return;
      update(mode, (state) => ({ activeSessionId: session.id, messages: [], chatInput: '', sessions: [session, ...state.sessions] }));
    } catch (error) { if (requestEpoch === epoch.current) update(mode, { error: error instanceof Error ? error.message : 'Could not create a chat.' }); }
    finally { if (requestEpoch === epoch.current) update(mode, { loading: false }); }
  }, [cancelMessage, update]);

  const openConversation = useCallback(async (id: string) => {
    cancelMessage(); const mode = modeRef.current; const requestEpoch = epoch.current;
    update(mode, { activeSessionId: id, messages: [], loading: true, error: null });
    try {
      const result = await apiGetConversation(id, mode);
      if (requestEpoch === epoch.current) update(mode, { messages: messagesFromHistory(result.messages), memoryBackend: result.memoryBackend });
    } catch (error) { if (requestEpoch === epoch.current) update(mode, { error: error instanceof Error ? error.message : 'Could not load this chat.' }); }
    finally { if (requestEpoch === epoch.current) update(mode, { loading: false }); }
  }, [cancelMessage, update]);

  const deleteConversation = useCallback(async (id: string) => {
    cancelMessage(); const mode = modeRef.current; const requestEpoch = epoch.current;
    try {
      await apiDeleteSession(id, mode);
      if (requestEpoch === epoch.current) update(mode, (state) => ({ sessions: state.sessions.filter((session) => session.id !== id),
        ...(state.activeSessionId === id ? { activeSessionId: null, messages: [] } : {}) }));
    } catch (error) { if (requestEpoch === epoch.current) update(mode, { error: error instanceof Error ? error.message : 'Could not delete chat.' }); }
  }, [cancelMessage, update]);

  const sendMessage = useCallback(async () => {
    const mode = modeRef.current; const current = stateRef.current[mode];
    const text = current.chatInput.trim();
    if (!text || current.busy || controller.current) return;
    const requestEpoch = ++epoch.current;
    const abort = new AbortController(); controller.current = abort;
    update(mode, { busy: true, error: null });
    let sessionId = current.activeSessionId;
    const draftId = `draft-${requestEpoch}`;
    try {
      if (!sessionId) {
        const session = await apiCreateSession(mode);
        if (requestEpoch !== epoch.current) return;
        sessionId = session.id;
        update(mode, (state) => ({ activeSessionId: session.id, sessions: [session, ...state.sessions] }));
      }
      update(mode, (state) => ({ chatInput: '', messages: [...state.messages,
        { id: `user-${requestEpoch}`, sender: 'user', text, timestamp: new Date().toISOString() },
        { id: draftId, sender: 'oracle', text: '', timestamp: new Date().toISOString(), streaming: true }] }));
      const answer = await apiStreamConversation(sessionId, { question: text, workspace: mode, task: current.task, answerFormat: current.answerFormat }, (delta) => {
        if (requestEpoch !== epoch.current) return;
        update(mode, (state) => ({ messages: state.messages.map((message) => message.id === draftId ? { ...message, text: message.text + delta } : message) }));
      }, abort.signal);
      if (requestEpoch !== epoch.current) return;
      update(mode, { messages: messagesFromHistory(answer.history, answer), memoryBackend: answer.memoryBackend });
      void refreshSessions(mode);
    } catch (error) {
      if (requestEpoch !== epoch.current || abort.signal.aborted) return;
      update(mode, (state) => ({ messages: state.messages.filter((message) => message.id !== draftId && message.id !== `user-${requestEpoch}`), chatInput: text,
        error: error instanceof Error ? error.message : 'The answer is unavailable. Please retry.' }));
    } finally {
      if (requestEpoch === epoch.current) { update(mode, { busy: false }); controller.current = null; }
    }
  }, [update, refreshSessions]);

  const applyVoiceAnswer = useCallback((answer: VoiceServerAnswer) => {
    update(workspace, { messages: messagesFromHistory(answer.history, answer), memoryBackend: answer.memoryBackend });
    void refreshSessions(workspace);
  }, [workspace, update, refreshSessions]);
  const current = states[workspace];
  return { ...current, sessionsLoading: current.loading, chatError: current.error, isSending: current.busy,
    isConversationMode: current.activeSessionId !== null, startNewConversation, openConversation, deleteConversation,
    sendMessage, cancelMessage, applyVoiceAnswer,
    setChatInput: (chatInput: string) => update(workspace, { chatInput }),
    setAnswerFormat: (answerFormat: '5' | '10' | '15') => update(workspace, { answerFormat }),
    setTask: (task: WorkspaceTask) => update(workspace, { task }),
    setMemoryBackend: (memoryBackend: string) => update(workspace, { memoryBackend }),
    backToHomepage: () => { cancelMessage(); update(workspace, { activeSessionId: null, messages: [] }); },
  };
}
