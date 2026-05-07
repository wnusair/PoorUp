import { useState } from 'react';
import LiberalDemocracyRail from '../Game/LiberalDemocracyRail';

const PANEL_TABS = [
  { key: 'portfolio', label: 'Portfolio' },
  { key: 'market', label: 'Market' },
  { key: 'bank', label: 'Bank' },
  { key: 'work', label: 'Work' },
  { key: 'taxes', label: 'Taxes' },
  { key: 'politics', label: 'Politics' },
];

function TabButton({ active, label, onClick }) {
  return (
    <button
      onClick={onClick}
      className={[
        'rounded-full px-3 py-2 text-xs font-semibold uppercase tracking-wide transition',
        active
          ? 'border border-cyan-700 bg-cyan-950/60 text-cyan-200'
          : 'border border-gray-800 bg-gray-950 text-gray-400 hover:border-gray-700 hover:text-gray-200',
      ].join(' ')}
    >
      {label}
    </button>
  );
}

export default function LiberalDemocracyPanelModal({ socketActions = {}, onClose }) {
  const [activePanel, setActivePanel] = useState('portfolio');

  return (
    <div className="modal-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose?.(); }}>
      <div className="w-full max-w-7xl max-h-[calc(100vh-2rem)] overflow-hidden rounded-3xl border border-gray-800 bg-gray-950 shadow-2xl flex flex-col">
        <div className="border-b border-gray-800 bg-gray-950 px-6 py-5 flex-shrink-0">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-cyan-400">Liberal Democracy</p>
              <h2 className="mt-2 text-2xl font-bold text-white">Market &amp; Finance</h2>
              <p className="mt-1 text-sm text-gray-400">
                Stocks, crypto, banking, employment, and political mechanics for the Liberal Democracy regime.
              </p>
            </div>
            <button onClick={onClose} className="btn-ghost btn-sm">
              Close
            </button>
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            {PANEL_TABS.map(({ key, label }) => (
              <TabButton
                key={key}
                active={activePanel === key}
                label={label}
                onClick={() => setActivePanel(key)}
              />
            ))}
          </div>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-5">
          <LiberalDemocracyRail
            socketActions={socketActions}
            activePanel={activePanel}
            onPanelChange={setActivePanel}
            embedded
          />
        </div>
      </div>
    </div>
  );
}
