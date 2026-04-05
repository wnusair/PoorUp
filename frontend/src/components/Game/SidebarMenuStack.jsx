import { useGameStore } from '../../hooks/useGameState';

export default function SidebarMenuStack() {
  const { settings, setActiveModal } = useGameStore();

  const actions = [
    {
      key: 'stability',
      label: 'Open Stability Panel',
      className: 'border-rose-700/70 bg-rose-950/30 text-rose-200 hover:border-rose-500 hover:text-white',
    },
    {
      key: 'taxation',
      label: 'Open Economy Panel',
      className: 'border-cyan-700/70 bg-cyan-950/30 text-cyan-200 hover:border-cyan-500 hover:text-white',
    },
    settings?.trading_enabled !== false
      ? {
          key: 'trade',
          label: 'Open Trade Desk',
          className: 'border-amber-700/70 bg-amber-950/30 text-amber-200 hover:border-amber-500 hover:text-white',
        }
      : null,
    settings?.deals_enabled !== false
      ? {
          key: 'deals',
          label: 'Open Deals Desk',
          className: 'border-emerald-700/70 bg-emerald-950/30 text-emerald-200 hover:border-emerald-500 hover:text-white',
        }
      : null,
    settings?.lobbying_enabled
      ? {
          key: 'lobby',
          label: 'Open Lobbying Panel',
          className: 'border-purple-700/70 bg-purple-950/30 text-purple-200 hover:border-purple-500 hover:text-white',
        }
      : null,
  ].filter(Boolean);

  return (
    <div className="bg-gray-800 rounded-xl p-3 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Panels</h3>
        <span className="text-[11px] text-gray-500">Menu stack</span>
      </div>

      <div className="grid gap-2">
        {actions.map((action) => (
          <button
            key={action.key}
            type="button"
            onClick={() => setActiveModal(action.key)}
            className={`w-full rounded-lg border px-3 py-2 text-xs font-semibold transition ${action.className}`}
          >
            {action.label}
          </button>
        ))}
      </div>
    </div>
  );
}