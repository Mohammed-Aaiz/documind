import React, { useRef, useState } from 'react';
import { Page } from '../types';
import { useWorkspace } from '../context/WorkspaceContext';

interface WorkspacePageProps {
  onNavigate: (page: Page) => void;
}

export const WorkspacePage: React.FC<WorkspacePageProps> = () => {
  const { files, uploading, uploadError, addFiles, removeFile, messages, chatInput, setChatInput, sendMessage } = useWorkspace();
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const hasFiles = files.length > 0;

  const handleFiles = (rawFiles: FileList | null) => {
    if (!rawFiles) return;
    addFiles(Array.from(rawFiles));
    setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const typeIcon = (type: string) => {
    if (type === 'pdf') return 'picture_as_pdf';
    if (type === 'docx') return 'description';
    return 'article';
  };

  const statusIcon = (status: string) => {
    if (status === 'uploading') return 'cloud_upload';
    if (status === 'processing') return 'hourglass_top';
    if (status === 'error') return 'error';
    return 'check_circle';
  };

  const statusColor = (status: string) => {
    if (status === 'uploading') return 'text-cyber-cyan';
    if (status === 'processing') return 'text-yellow-400';
    if (status === 'error') return 'text-red-400';
    return 'text-green-400';
  };

  return (
    <div className="pt-24 pb-0 min-h-screen flex flex-col relative z-10 overflow-hidden">
      <div className="flex-1 flex flex-col items-center justify-center relative min-h-0">
        {!hasFiles ? (
          /* Drop zone */
          <div className="w-full max-w-2xl mx-auto px-4 md:px-8 relative">
            {/* Decorative orbit rings */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none" aria-hidden="true">
              <div className="absolute rounded-full border border-white/10 opacity-20"
                style={{ width: 500, height: 500, top: '50%', left: '50%', transform: 'translate(-50%,-50%)' }} />
              <div className="absolute rounded-full border border-cyber-cyan/30 opacity-40"
                style={{ width: 380, height: 380, top: '50%', left: '50%', transform: 'translate(-50%,-50%) rotateX(60deg) rotateY(20deg)' }} />
            </div>

            {/* Drop zone panel */}
            <div
              onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`rounded-2xl p-8 md:p-12 text-center relative z-10 cursor-pointer transition-all duration-500 ${
                isDragging ? 'border-cyber-cyan/70 shadow-[0_0_50px_rgba(6,182,212,0.3)]' : 'border-electric-violet/20 hover:border-cyber-cyan/50 hover:shadow-[0_0_40px_rgba(6,182,212,0.2)]'
              }`}
              style={{
                background: 'rgba(5,7,10,0.60)',
                backdropFilter: 'blur(20px)',
                WebkitBackdropFilter: 'blur(20px)',
                borderTop: '1px solid rgba(255,255,255,0.1)',
                borderLeft: '1px solid rgba(255,255,255,0.1)',
              }}
            >
              <span className="material-symbols-outlined text-cyber-cyan mb-6 animate-pulse block" style={{ fontSize: '64px' }}>
                model_training
              </span>
              <h2
                className="font-bold mb-4 bg-clip-text text-transparent"
                style={{
                  fontSize: 'clamp(32px, 6vw, 56px)',
                  lineHeight: 1.1,
                  letterSpacing: '-0.04em',
                  backgroundImage: 'linear-gradient(90deg, #8B5CF6, #06B6D4)',
                  fontFamily: 'Geist',
                }}
              >
                Awaiting Input
              </h2>
              <p className="text-outline mb-8 max-w-md mx-auto" style={{ fontFamily: 'Inter', fontSize: '16px', lineHeight: 1.6 }}>
                Drop PDF, DOCX, or TXT files here to initiate document analysis and extract actionable intelligence.
              </p>

              {uploadError && (
                <div className="mb-6 p-3 rounded bg-error/10 border border-error/30 text-error text-xs font-mono max-w-md mx-auto">
                  {uploadError}
                </div>
              )}

              <div className="flex justify-center gap-4">
                <button
                  onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}
                  className="px-6 md:px-8 py-4 rounded-lg text-on-surface hover:bg-surface-bright/50 transition-all flex items-center gap-2"
                  style={{
                    fontFamily: 'JetBrains Mono',
                    fontSize: '12px',
                    background: 'rgba(50,53,57,0.8)',
                    border: '1px solid rgba(255,255,255,0.1)',
                  }}
                >
                  <span className="material-symbols-outlined text-sm">upload_file</span>
                  Select Files
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}
                  className="px-6 md:px-8 py-4 rounded-lg text-white transition-all flex items-center gap-2"
                  style={{
                    fontFamily: 'JetBrains Mono',
                    fontSize: '12px',
                    background: 'linear-gradient(90deg, #8B5CF6, #06B6D4)',
                    boxShadow: '0 0 15px rgba(6,182,212,0.3)',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.boxShadow = '0 0 30px rgba(139,92,246,0.6)')}
                  onMouseLeave={(e) => (e.currentTarget.style.boxShadow = '0 0 15px rgba(6,182,212,0.3)')}
                >
                  <span className="material-symbols-outlined text-sm">radar</span>
                  Initiate Scan
                </button>
              </div>
              <input ref={fileInputRef} type="file" multiple accept=".pdf,.docx,.txt" className="hidden" onChange={(e) => handleFiles(e.target.files)} />
            </div>
          </div>
        ) : (
          /* Workspace with files + chat */
          <div className="w-full max-w-4xl mx-auto flex gap-6 h-full px-4 md:px-8">
            {/* Uploaded files panel */}
            <div className="w-48 md:w-64 flex-shrink-0 flex flex-col gap-3">
              <div className="flex items-center justify-between mb-1">
                <h3 className="text-outline" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px', letterSpacing: '0.1em', fontWeight: 700 }}>DOCUMENTS</h3>
                <button onClick={() => fileInputRef.current?.click()} className="text-electric-violet hover:text-primary transition-colors">
                  <span className="material-symbols-outlined text-[18px]">add</span>
                </button>
              </div>

              {uploading && (
                <div className="flex items-center gap-2 p-2 text-cyber-cyan" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px' }}>
                  <span className="material-symbols-outlined text-[14px] animate-spin">progress_activity</span>
                  Uploading...
                </div>
              )}

              <div className="flex flex-col gap-2 overflow-y-auto max-h-96 pr-1">
                {files.map((f) => (
                  <div key={f.id} className="flex items-center gap-3 p-3 rounded-lg transition-colors hover:bg-surface-bright/10 group"
                    style={{ background: 'rgba(5,7,10,0.60)', backdropFilter: 'blur(20px)', borderTop: '1px solid rgba(255,255,255,0.1)', borderLeft: '1px solid rgba(255,255,255,0.1)' }}>
                    <span className={`material-symbols-outlined text-[20px] ${f.status === 'error' ? 'text-red-400' : 'text-electric-violet'}`}>{typeIcon(f.type)}</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-on-surface truncate text-xs" style={{ fontFamily: 'Inter', fontSize: '14px' }}>{f.name}</p>
                      <div className="flex items-center gap-2">
                        <p className="text-outline" style={{ fontFamily: 'JetBrains Mono', fontSize: '12px' }}>{f.size}</p>
                        {f.status !== 'ready' && f.status !== 'error' && (
                          <span className={`material-symbols-outlined animate-spin ${statusColor(f.status)}`} style={{ fontSize: '10px' }}>progress_activity</span>
                        )}
                        <span className={`material-symbols-outlined ${statusColor(f.status)}`} style={{ fontSize: '12px' }}>{statusIcon(f.status)}</span>
                      </div>
                      {f.status === 'ready' && f.chunkCount > 0 && (
                        <p className="text-cyber-cyan" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px' }}>{f.chunkCount} chunks</p>
                      )}
                      {f.status === 'error' && (
                        <p className="text-red-400" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px' }}>Failed</p>
                      )}
                    </div>
                    <button
                      onClick={() => removeFile(f.id)}
                      className="opacity-0 group-hover:opacity-100 text-outline hover:text-error transition-all"
                      title="Remove"
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>close</span>
                    </button>
                  </div>
                ))}
              </div>
              <input ref={fileInputRef} type="file" multiple accept=".pdf,.docx,.txt" className="hidden" onChange={(e) => handleFiles(e.target.files)} />
            </div>

            {/* Chat panel */}
            <div className="flex-1 flex flex-col rounded-xl overflow-hidden min-w-0"
              style={{ background: 'rgba(5,7,10,0.60)', backdropFilter: 'blur(20px)', borderTop: '1px solid rgba(255,255,255,0.1)', borderLeft: '1px solid rgba(255,255,255,0.1)' }}>
              <div className="p-4 border-b border-white/5 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-cyber-cyan animate-pulse" />
                <span className="text-cyber-cyan" style={{ fontFamily: 'JetBrains Mono', fontSize: '12px' }}>Oracle Active</span>
              </div>
              <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">
                {messages.length === 0 && (
                  <p className="text-center text-outline mt-8" style={{ fontFamily: 'Inter', fontSize: '14px' }}>
                    Ask the Oracle anything about your documents.
                  </p>
                )}
                {messages.map((msg) => (
                  <div key={msg.id} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div
                      className="max-w-[80%] px-4 py-3 rounded-xl"
                      style={
                        msg.sender === 'user'
                          ? { background: 'linear-gradient(135deg, rgba(139,92,246,0.3), rgba(6,182,212,0.2))', border: '1px solid rgba(139,92,246,0.3)', color: '#e1e2e7', fontFamily: 'Inter', fontSize: '14px' }
                          : { background: 'rgba(29,32,35,0.8)', border: '1px solid rgba(255,255,255,0.08)', color: '#cbc3d7', fontFamily: 'Inter', fontSize: '14px' }
                      }
                    >
                      {msg.sender === 'oracle' && (
                        <span className="text-electric-violet block mb-1" style={{ fontFamily: 'JetBrains Mono', fontSize: '12px' }}>Oracle</span>
                      )}
                      {msg.text}
                      {msg.insufficientContext && (
                        <span className="block mt-2 text-yellow-400" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px' }}>
                          Insufficient context in documents to answer this question.
                        </span>
                      )}
                      {msg.sources && msg.sources.length > 0 && (
                        <div className="mt-3 pt-2 border-t border-white/10">
                          <span className="text-outline block mb-1" style={{ fontFamily: 'JetBrains Mono', fontSize: '9px', letterSpacing: '0.1em' }}>SOURCES</span>
                          {msg.sources.slice(0, 3).map((src) => (
                            <div key={src.chunkId} className="flex items-center gap-2 mb-1">
                              <span className="text-cyber-cyan" style={{ fontFamily: 'JetBrains Mono', fontSize: '9px' }}>
                                {src.documentName}{src.page ? ` p.${src.page}` : ''}
                              </span>
                              <span className="text-outline" style={{ fontFamily: 'JetBrains Mono', fontSize: '9px' }}>
                                {(src.score * 100).toFixed(0)}%
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Bottom floating command bar */}
      <div className="fixed bottom-6 left-1/2 -translate-x-1/2 w-[calc(100%-2rem)] md:w-[600px] z-50" style={{ marginLeft: 'clamp(0px, calc(50% - 300px), 128px)' }}>
        <div
          className="rounded-full p-2 flex items-center gap-3"
          style={{
            background: 'rgba(5,7,10,0.70)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            borderTop: '1px solid rgba(255,255,255,0.1)',
            borderLeft: '1px solid rgba(255,255,255,0.1)',
            boxShadow: '0 10px 40px rgba(0,0,0,0.8), 0 0 20px rgba(6,182,212,0.2)',
          }}
        >
          <button
            className="w-10 h-10 rounded-full flex items-center justify-center text-cyber-cyan hover:bg-surface-bright transition-colors flex-shrink-0"
            style={{ background: 'rgba(29,32,35,1)' }}
            title="Voice input"
          >
            <span className="material-symbols-outlined text-xl">mic</span>
          </button>
          <input
            type="text"
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Command the Oracle..."
            className="flex-1 bg-transparent border-none text-on-surface focus:outline-none focus:ring-0 placeholder:text-outline-variant text-sm"
            style={{ fontFamily: 'Inter', fontSize: '16px' }}
          />
          <button
            onClick={sendMessage}
            className="w-10 h-10 rounded-full flex items-center justify-center text-white hover:shadow-[0_0_15px_rgba(6,182,212,0.5)] transition-all flex-shrink-0"
            style={{ background: 'linear-gradient(135deg, #8B5CF6, #06B6D4)' }}
            title="Send"
          >
            <span className="material-symbols-outlined text-xl">send</span>
          </button>
        </div>
      </div>
    </div>
  );
};
