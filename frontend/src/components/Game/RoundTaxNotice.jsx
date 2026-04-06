import { useEffect, useMemo, useRef, useState } from 'react';
import { useGameStore } from '../../hooks/useGameState';
import { buildPlayerTaxSchedule, formatTaxRate, getEffectiveTaxRate } from '../../utils/economy';
import { formatExactMoney } from '../../utils/formatters';

export default function RoundTaxNotice({ myPlayerId, onOpenDetails }) {
  const players = useGameStore((state) => state.players);
  const properties = useGameStore((state) => state.properties);
  const economy = useGameStore((state) => state.economy);
  const settings = useGameStore((state) => state.settings);
  const currentPlayerId = useGameStore((state) => state.currentPlayerId);

  const [visible, setVisible] = useState(false);
  const lastShownKeyRef = useRef('');

  const currentRound = Math.max(
    1,
    Number(economy?.current_round ?? economy?.round_number ?? 1) || 1,
  );

  const me = useMemo(
    () => players.find((player) => player.id === myPlayerId) || null,
    [players, myPlayerId],
  );

  const ownedProperties = useMemo(
    () => Object.values(properties || {}).filter((property) => property?.owner_id === myPlayerId),
    [properties, myPlayerId],
  );

  const schedule = useMemo(
    () => buildPlayerTaxSchedule({
      player: me,
      properties: ownedProperties,
      economy,
      settings,
      currentRound,
    }),
    [me, ownedProperties, economy, settings, currentRound],
  );

  const effectiveTaxRate = getEffectiveTaxRate(economy);

  useEffect(() => {
    if (!myPlayerId || !me || currentPlayerId !== myPlayerId) {
      return;
    }

    const nextKey = `${myPlayerId}:${currentRound}`;
    if (lastShownKeyRef.current === nextKey) {
      return;
    }

    lastShownKeyRef.current = nextKey;
    setVisible(true);
  }, [myPlayerId, me, currentPlayerId, currentRound]);

  if (!visible || !me || !schedule.length) {
    return null;
  }

  return (
    <div className="pointer-events-none absolute left-4 top-4 z-30 max-w-sm">
      <div className="pointer-events-auto rounded-2xl border border-cyan-900/70 bg-slate-950/95 shadow-2xl shadow-cyan-950/30 backdrop-blur">
        <div className="flex items-start justify-between gap-3 border-b border-slate-800 px-4 py-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-cyan-300">Round {currentRound} Taxes</p>
            <p className="mt-1 text-sm text-slate-200">Cash-tax rate: <span className="font-semibold text-white">{formatTaxRate(effectiveTaxRate)}</span></p>
          </div>
          <button
            type="button"
            onClick={() => setVisible(false)}
            className="rounded-lg border border-slate-700 px-2.5 py-1 text-xs font-semibold uppercase tracking-wide text-slate-300 transition hover:border-slate-500 hover:text-white"
          >
            Dismiss
          </button>
        </div>

        <div className="space-y-2 px-3 py-3">
          {schedule.map((item) => (
            <div
              key={item.id}
              className={[
                'rounded-xl border px-3 py-2',
                item.enabled
                  ? item.dueThisRound
                    ? 'border-amber-700/70 bg-amber-950/20'
                    : 'border-slate-800 bg-slate-900/80'
                  : 'border-slate-900 bg-slate-950/80 opacity-80',
              ].join(' ')}
            >
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-white">{item.label}</p>
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
                    {item.enabled ? (item.dueThisRound ? 'Due This Round' : 'Active Rule') : 'Disabled'}
                  </p>
                </div>
                <p className="text-sm font-semibold text-cyan-200">{formatExactMoney(item.amount)}</p>
              </div>
              <p className="mt-2 text-xs text-slate-300">{item.when}</p>
              <p className="mt-1 text-xs text-slate-500">{item.detail}</p>
            </div>
          ))}
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-slate-800 px-4 py-3 text-xs text-slate-400">
          <p>Estimates use your current cash and property values at the start of the round.</p>
          <button
            type="button"
            onClick={onOpenDetails}
            className="whitespace-nowrap rounded-lg border border-cyan-800/70 px-3 py-1.5 font-semibold uppercase tracking-wide text-cyan-200 transition hover:border-cyan-600 hover:text-white"
          >
            Full Breakdown
          </button>
        </div>
      </div>
    </div>
  );
}