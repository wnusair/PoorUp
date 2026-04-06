import { useEffect, useMemo, useRef, useState } from 'react';
import { useGameStore } from '../../hooks/useGameState';
import { buildPlayerTaxSchedule, formatTaxRate, getEffectiveTaxRate } from '../../utils/economy';
import { formatExactMoney } from '../../utils/formatters';

function RecurringBadge({ label, amount, tone }) {
  if (!amount) {
    return null;
  }

  return (
    <span
      className={[
        'inline-flex items-center rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em]',
        tone,
      ].join(' ')}
    >
      {label} {formatExactMoney(amount)}
    </span>
  );
}

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
  const guaranteedPerTurn = useMemo(
    () => schedule.reduce((sum, item) => sum + (Number(item.perTurnAmount) || 0), 0),
    [schedule],
  );
  const guaranteedPerRotation = useMemo(
    () => schedule.reduce((sum, item) => sum + (Number(item.perRotationAmount) || 0), 0),
    [schedule],
  );

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
    <div className="absolute inset-0 z-30 overflow-y-auto px-4 py-4 sm:px-6 sm:py-6">
      <div className="flex min-h-full items-start justify-center sm:items-center">
        <div className="pointer-events-auto my-auto w-full max-w-5xl rounded-3xl border border-cyan-900/70 bg-slate-950/95 shadow-2xl shadow-cyan-950/30 backdrop-blur">
        <div className="flex items-start justify-between gap-4 border-b border-slate-800 px-5 py-4">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-cyan-300">Round {currentRound} Taxes</p>
            <p className="mt-1 text-sm text-slate-200">Cash-tax rate: <span className="font-semibold text-white">{formatTaxRate(effectiveTaxRate)}</span></p>
            <p className="mt-2 text-xs text-slate-400">Recurring turn and rotation costs are called out directly on the rules that apply.</p>
          </div>
          <button
            type="button"
            onClick={() => setVisible(false)}
            className="rounded-lg border border-slate-700 px-2.5 py-1 text-xs font-semibold uppercase tracking-wide text-slate-300 transition hover:border-slate-500 hover:text-white"
          >
            Dismiss
          </button>
        </div>

        <div className="grid gap-3 border-b border-slate-800/80 px-5 py-4 sm:grid-cols-2">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/80 px-4 py-3">
            <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Guaranteed Per Turn</p>
            <p className="mt-2 text-lg font-semibold text-emerald-300">{formatExactMoney(guaranteedPerTurn)}</p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-900/80 px-4 py-3">
            <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Guaranteed Per Rotation</p>
            <p className="mt-2 text-lg font-semibold text-amber-300">{formatExactMoney(guaranteedPerRotation)}</p>
          </div>
        </div>

        <div className="grid gap-3 px-5 py-4 md:grid-cols-2 xl:grid-cols-3">
          {schedule.map((item) => (
            <div
              key={item.id}
              className={[
                'rounded-2xl border px-4 py-4',
                item.enabled
                  ? item.dueThisRound
                    ? 'border-amber-700/70 bg-amber-950/20'
                    : 'border-slate-800 bg-slate-900/80'
                  : 'border-slate-900 bg-slate-950/80 opacity-80',
              ].join(' ')}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-white">{item.label}</p>
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
                    {item.enabled ? (item.dueThisRound ? 'Due This Round' : 'Active Rule') : 'Disabled'}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">On Trigger</p>
                  <p className="mt-1 text-lg font-semibold text-cyan-200">{formatExactMoney(item.amount)}</p>
                </div>
              </div>

              {(item.perTurnAmount || item.perRotationAmount) && (
                <div className="mt-3 flex flex-wrap gap-2">
                  <RecurringBadge
                    label="Per Turn"
                    amount={item.perTurnAmount}
                    tone="border-emerald-800/70 bg-emerald-950/40 text-emerald-200"
                  />
                  <RecurringBadge
                    label="Per Rotation"
                    amount={item.perRotationAmount}
                    tone="border-amber-800/70 bg-amber-950/40 text-amber-200"
                  />
                </div>
              )}

              <p className="mt-3 text-xs text-slate-300">{item.when}</p>
              <p className="mt-1 text-xs text-slate-500">{item.detail}</p>
            </div>
          ))}
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-slate-800 px-5 py-4 text-xs text-slate-400">
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
    </div>
  );
}