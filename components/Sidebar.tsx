'use client';

interface SidebarProps {
  activeTab: string;
  onTabClick: (tab: string) => void;
  onExecuteClick: () => void;
}

export default function Sidebar({ activeTab, onTabClick, onExecuteClick }: SidebarProps) {
  return (
    <aside className="hidden xl:flex bg-surface-container-low/95 backdrop-blur-lg docked left-0 h-full w-80 border-r border-outline-variant/10 shadow-[10px_0_30px_rgba(0,0,0,0.3)] flex-col py-8 px-4 gap-stack-md z-40">
      {/* Header section */}
      <div className="px-4 mb-6">
        <h2 className="font-display-lg text-headline-md text-on-surface uppercase tracking-widest">
          DUGOUT CONTROL
        </h2>
        <p className="font-label-sm text-label-sm text-primary mt-1">
          Tactical Command
        </p>
      </div>

      {/* Nav section */}
      <nav className="flex-1 flex flex-col gap-1.5">
        <button 
          onClick={() => onTabClick('AI Consultant')}
          className={`flex items-center gap-4 px-4 py-2.5 transition-all text-left w-full ${
            activeTab === 'AI Consultant'
              ? 'bg-primary-container text-on-primary-container font-bold border-l-4 border-secondary translate-x-1'
              : 'text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface hover:backdrop-brightness-125'
          }`}
        >
          <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>
            psychology
          </span>
          <span className="font-body-md text-body-md uppercase tracking-widest">
            Diziliş
          </span>
        </button>

        <button 
          onClick={() => onTabClick('Substitutions')}
          className={`flex items-center gap-4 px-4 py-2.5 transition-all text-left w-full ${
            activeTab === 'Substitutions'
              ? 'bg-primary-container text-on-primary-container font-bold border-l-4 border-secondary translate-x-1'
              : 'text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface hover:backdrop-brightness-125'
          }`}
        >
          <span className="material-symbols-outlined">swap_vert</span>
          <span className="font-body-md text-body-md uppercase tracking-widest">
            Substitutions
          </span>
        </button>

        <button 
          onClick={() => onTabClick('Matchday')}
          className={`flex items-center gap-4 px-4 py-2.5 transition-all text-left w-full ${
            activeTab === 'Matchday'
              ? 'bg-primary-container text-on-primary-container font-bold border-l-4 border-secondary translate-x-1'
              : 'text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface hover:backdrop-brightness-125'
          }`}
        >
          <span className="material-symbols-outlined">sports_soccer</span>
          <span className="font-body-md text-body-md uppercase tracking-widest">
            Matchday
          </span>
        </button>

        <button 
          onClick={() => onTabClick('Analytics')}
          className={`flex items-center gap-4 px-4 py-2.5 transition-all text-left w-full ${
            activeTab === 'Analytics'
              ? 'bg-primary-container text-on-primary-container font-bold border-l-4 border-secondary translate-x-1'
              : 'text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface hover:backdrop-brightness-125'
          }`}
        >
          <span className="material-symbols-outlined">query_stats</span>
          <span className="font-body-md text-body-md uppercase tracking-widest">
            Analytics
          </span>
        </button>

        <button 
          onClick={() => onTabClick('Finance')}
          className={`flex items-center gap-4 px-4 py-2.5 transition-all text-left w-full ${
            activeTab === 'Finance'
              ? 'bg-primary-container text-on-primary-container font-bold border-l-4 border-secondary translate-x-1'
              : 'text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface hover:backdrop-brightness-125'
          }`}
        >
          <span className="material-symbols-outlined">payments</span>
          <span className="font-body-md text-body-md uppercase tracking-widest">
            Finance
          </span>
        </button>

        <button 
          onClick={() => onTabClick('Settings')}
          className={`flex items-center gap-4 px-4 py-2.5 transition-all text-left w-full ${
            activeTab === 'Settings'
              ? 'bg-primary-container text-on-primary-container font-bold border-l-4 border-secondary translate-x-1'
              : 'text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface hover:backdrop-brightness-125'
          }`}
        >
          <span className="material-symbols-outlined">settings</span>
          <span className="font-body-md text-body-md uppercase tracking-widest">
            Settings
          </span>
        </button>
      </nav>

      {/* Execute button */}
      <button 
        onClick={onExecuteClick}
        className="emerald-gradient font-display-lg text-body-md uppercase text-on-primary px-4 py-3 rounded-sm shadow-lg hover:brightness-110 transition-all mt-auto mb-4 mx-4"
      >
        EXECUTE CHANGES
      </button>

      {/* Footer section */}
      <div className="flex flex-col gap-2 border-t border-outline-variant/20 pt-4 px-4">
        <a
          href="#"
          className="flex items-center gap-4 py-2 text-on-surface-variant hover:text-on-surface transition-all"
        >
          <span className="material-symbols-outlined">help</span>
          <span className="font-label-sm text-label-sm uppercase tracking-widest">
            Support
          </span>
        </a>
        <a
          href="#"
          className="flex items-center gap-4 py-2 text-on-surface-variant hover:text-on-surface transition-all"
        >
          <span className="material-symbols-outlined">logout</span>
          <span className="font-label-sm text-label-sm uppercase tracking-widest">
            Log Out
          </span>
        </a>
      </div>
    </aside>
  );
}
