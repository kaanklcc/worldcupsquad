import { useState } from 'react';
import { ChatMessage, SuggestedAction, Player } from '@/types';

interface ChatPanelProps {
  messages: ChatMessage[];
  onSendMessage: (prompt: string, isPremium: boolean) => void;
  onApproveAction: (action: SuggestedAction) => void;
  isLoading: boolean;
  pendingAction: SuggestedAction | null;
  sellPlayer: Player | null;
  buyPlayer: Player | null;
}

export default function ChatPanel({
  messages,
  onSendMessage,
  onApproveAction,
  isLoading,
  pendingAction,
  sellPlayer,
  buyPlayer,
}: ChatPanelProps) {
  const [input, setInput] = useState('');

  const handleSendFree = () => {
    if (!input.trim()) return;
    onSendMessage(input, false);
    setInput('');
  };

  const handleSendPremium = () => {
    const promptText = input.trim() || 'Analyse my squad and suggest the best transfer';
    onSendMessage(promptText, true);
    setInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSendFree();
    }
  };

  return (
    <aside className="hidden lg:flex w-80 xl:w-96 flex-col border-l border-outline-variant/20 z-40 relative flex-shrink-0">
      {/* Leather texture bg */}
      <div className="absolute inset-0 leather-texture z-0 border-l border-outline-variant/30"></div>

      {/* Content */}
      <div className="relative z-10 flex flex-col h-full p-4 xl:p-6">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8 border-b border-outline-variant/30 pb-4">
          <span className="material-symbols-outlined text-3xl text-secondary">
            smart_toy
          </span>
          <h2 className="font-display-lg text-headline-md uppercase tracking-tight text-on-surface">
            Auto-Gaffer AI
          </h2>
        </div>

        {/* Chat messages area */}
        <div className="flex-1 flex flex-col gap-3 mb-4 overflow-y-auto scrollbar-thin">
          {messages.length === 0 ? (
            <p className="text-on-surface-variant/50 text-sm italic text-center mt-10">
              Ask the AI consultant about your squad...
            </p>
          ) : (
            messages.map((msg) => (
              <div
                key={msg.id}
                className={
                  msg.role === 'assistant'
                    ? `bg-surface-container/80 backdrop-blur-md p-4 rounded-lg shadow-inner ${
                        msg.isPremium
                          ? 'border border-primary/30'
                          : 'border border-outline-variant/30'
                      }`
                    : 'bg-primary-container/30 p-3 rounded-lg border border-primary/20 ml-8'
                }
              >
                {msg.isPremium && msg.role === 'assistant' && (
                  <div className="text-primary text-[10px] font-bold tracking-wider mb-1">
                    PREMIUM ANALYSIS
                  </div>
                )}
                <p
                  className={`whitespace-pre-wrap ${
                    msg.role === 'assistant'
                      ? 'font-body-md text-body-md text-on-surface-variant'
                      : 'font-body-md text-body-md text-on-surface'
                  }`}
                >
                  {msg.content}
                </p>
              </div>
            ))
          )}

          {isLoading && (
            <div className="bg-surface-container/80 backdrop-blur-md p-4 rounded-lg border border-outline-variant/30 shadow-inner w-24 flex justify-center gap-1">
              <div className="w-2 h-2 bg-on-surface-variant rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
              <div className="w-2 h-2 bg-on-surface-variant rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
              <div className="w-2 h-2 bg-on-surface-variant rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
            </div>
          )}
        </div>

        {/* Substitution Proposal card */}
        {pendingAction && sellPlayer && buyPlayer && (
          <div className="glass-panel rounded-xl p-5 mb-4 border border-secondary/20 shadow-[0_8px_30px_rgba(0,0,0,0.5)]">
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-display-lg text-body-lg uppercase text-on-surface">
                Substitution Proposal
              </h3>
              <span className="material-symbols-outlined text-secondary animate-pulse">
                timer
              </span>
            </div>

            <div className="flex items-center justify-between bg-surface-container/50 rounded-lg p-3 border border-outline-variant/20 mb-4">
              {/* Out player */}
              <div className="flex flex-col items-center flex-1">
                <div className="w-12 h-12 rounded-full border border-error bg-surface flex items-center justify-center">
                  <span className="material-symbols-outlined text-error">person</span>
                </div>
                <span className="font-display-lg text-body-md uppercase text-on-surface mt-1">
                  {sellPlayer.name.split(' ').pop()}
                </span>
                <div className="flex items-center text-error mt-1">
                  <span className="material-symbols-outlined text-sm font-bold animate-bounce">
                    arrow_downward
                  </span>
                  <span className="font-label-sm text-[10px] uppercase font-bold">
                    Out
                  </span>
                </div>
              </div>

              {/* Swap Icon */}
              <span className="material-symbols-outlined text-3xl text-outline px-2">
                swap_horiz
              </span>

              {/* In player */}
              <div className="flex flex-col items-center flex-1">
                <div className="w-12 h-12 rounded-full border border-secondary bg-surface flex items-center justify-center glow-bloom">
                  <span className="material-symbols-outlined text-secondary">
                    person
                  </span>
                </div>
                <span className="font-display-lg text-body-md uppercase text-on-surface mt-1">
                  {buyPlayer.name.split(' ').pop()}
                </span>
                <div className="flex items-center text-secondary mt-1">
                  <span
                    className="material-symbols-outlined text-sm font-bold animate-bounce"
                    style={{ animationDirection: 'reverse' }}
                  >
                    arrow_upward
                  </span>
                  <span className="font-label-sm text-[10px] uppercase font-bold">
                    In
                  </span>
                </div>
              </div>
            </div>

            <button
              onClick={() => onApproveAction(pendingAction)}
              className="w-full emerald-gradient font-display-lg text-body-md uppercase text-on-primary py-3 rounded-sm shadow-lg hover:brightness-110 transition-all flex items-center justify-center gap-2"
            >
              <span className="material-symbols-outlined">check_circle</span>
              CONFIRM TACTICAL CHANGE
            </button>
          </div>
        )}

        {/* Input area */}
        <div className="mt-auto mb-4">
          <label className="font-label-sm text-label-sm text-on-surface-variant uppercase mb-2 block">
            Consult Assistant
          </label>
          <div className="relative">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              className="w-full bg-surface-dim border-0 border-b-2 border-outline-variant focus:border-secondary focus:ring-0 text-body-md text-on-surface py-3 px-4 font-body-md placeholder-outline rounded-t-md"
              placeholder="e.g., How do we counter their 4-4-2?"
              disabled={isLoading}
            />
            <button
              onClick={handleSendFree}
              disabled={isLoading}
              className="absolute right-2 top-1/2 transform -translate-y-1/2 text-secondary hover:text-primary transition-colors cursor-pointer disabled:opacity-50"
            >
              <span className="material-symbols-outlined">send</span>
            </button>
          </div>
        </div>

        {/* Premium Button */}
        <button
          onClick={handleSendPremium}
          disabled={isLoading}
          className="gold-gradient font-display-lg text-body-md uppercase w-full py-4 rounded-sm shadow-lg hover:brightness-110 transition-all flex justify-center items-center gap-3 disabled:opacity-50"
        >
          <span
            className="material-symbols-outlined"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            menu_book
          </span>
          UNLOCK DEEP TACTICAL ANALYTICS
        </button>
      </div>
    </aside>
  );
}
