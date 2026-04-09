import { useState } from 'react';
import { useGameStore } from '../../hooks/useGameState';
import { adminSeedPlotDebug } from '../../utils/api';

function getStoredUserId() {
  if (typeof globalThis === 'undefined' || !globalThis.localStorage) {
    return null;
  }

  try {
    const raw = globalThis.localStorage.getItem('poorup_user');
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw);
    const userId = Number(parsed?.id);
    return Number.isFinite(userId) ? userId : null;
  } catch {
    return null;
  }
}

function hostDebugToolsEnabled() {
  return import.meta.env.VITE_ENABLE_HOST_DEBUG_TOOLS !== 'false';
}

export default function SidebarMenuStack() {
  const { settings, setActiveModal, clearTrade, clearActiveDeal, matchId, lobbyData } = useGameStore();
  const [seedingPlot, setSeedingPlot] = useState(false);
  const [debugMessage, setDebugMessage] = useState('');
  const storedUserId = getStoredUserId();
  const isHost = storedUserId != null && Number(lobbyData?.match?.host_user_id) === storedUserId;
  const canUseHostDebugTools = hostDebugToolsEnabled();

  const actions = [
    {
      key: 'stability',
      label: 'Open Stability Panel',
      className: 'border-rose-700/70 bg-rose-950/30 text-rose-200 hover:border-rose-500 hover:text-white',
    },
    {
      key: 'plot',
      label: 'Open Plot Panel',
      className: 'border-red-700/70 bg-red-950/30 text-red-200 hover:border-red-500 hover:text-white',
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

  const handleSeedPlotDebug = async () => {
    if (!matchId || seedingPlot) {
      return;
    }
    setSeedingPlot(true);
    setDebugMessage('');
    try {
      const { data } = await adminSeedPlotDebug(matchId);
      setDebugMessage(data?.message || 'Communist plot debug state seeded.');
    } catch (error) {
      const message = error?.response?.data?.error || 'Failed to seed the communist plot debug state.';
      setDebugMessage(message);
    } finally {
      setSeedingPlot(false);
    }
  };

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
            onClick={() => {
              if (action.key === 'trade') {
                clearTrade();
              }
              if (action.key === 'deals') {
                clearActiveDeal();
              }
              setActiveModal(action.key);
            }}
            className={`w-full rounded-lg border px-3 py-2 text-xs font-semibold transition ${action.className}`}
          >
            {action.label}
          </button>
        ))}
      </div>

      {isHost && matchId && canUseHostDebugTools ? (
        <div className="rounded-lg border border-red-800/70 bg-red-950/25 p-2.5 space-y-2">
          <div className="flex items-center justify-between gap-2">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.24em] text-red-300">Host Debug</p>
              <p className="text-[11px] text-red-100/70">Seed a live communist-plot board with you as the revolutionary.</p>
            </div>
            <button
              type="button"
              onClick={handleSeedPlotDebug}
              disabled={seedingPlot}
              className="rounded-lg border border-red-600/70 bg-red-900/60 px-3 py-2 text-[11px] font-semibold text-red-50 transition hover:border-red-400 hover:bg-red-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {seedingPlot ? 'Seeding...' : 'Seed Plot'}
            </button>
          </div>
          {debugMessage ? (
            <p className="text-[11px] text-red-100/80">{debugMessage}</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}