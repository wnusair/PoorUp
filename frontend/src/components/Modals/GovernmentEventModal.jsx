import { useGameStore } from '../../hooks/useGameState';

const CATEGORY_COLORS = {
  war: 'border-red-700/60 bg-red-950/30',
  tax_cut: 'border-purple-700/60 bg-purple-950/30',
  stimulus: 'border-emerald-700/60 bg-emerald-950/30',
  austerity: 'border-amber-700/60 bg-amber-950/30',
  central_bank: 'border-sky-700/60 bg-sky-950/30',
  rate_cut: 'border-cyan-700/60 bg-cyan-950/30',
  strike: 'border-orange-700/60 bg-orange-950/30',
  boom: 'border-green-700/60 bg-green-950/30',
  crash: 'border-rose-700/60 bg-rose-950/30',
  election: 'border-fuchsia-700/60 bg-fuchsia-950/30',
};

const CATEGORY_ICONS = {
  war: '⚔️',
  tax_cut: '📉',
  stimulus: '💵',
  austerity: '✂️',
  central_bank: '🏦',
  rate_cut: '📈',
  strike: '✊',
  boom: '🚀',
  crash: '💥',
  election: '🗳️',
};

function EffectTag({ label, positive }) {
  return (
    <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${positive ? 'bg-emerald-950/60 text-emerald-300 border border-emerald-800/60' : 'bg-rose-950/60 text-rose-300 border border-rose-800/60'}`}>
      {positive ? '▲' : '▼'} {label}
    </span>
  );
}

function buildEffectTags(effects) {
  if (!effects) return [];
  const tags = [];
  const labels = {
    inflation_rate: (v) => ({ label: `Inflation ${v > 0 ? '+' : ''}${(v * 100).toFixed(1)}%`, positive: v < 0 }),
    interest_rate: (v) => ({ label: `Loan rate ${v > 0 ? '+' : ''}${(v * 100).toFixed(1)}%`, positive: v < 0 }),
    stability: (v) => ({ label: `Stability ${v > 0 ? '+' : ''}${(v * 100).toFixed(0)}%`, positive: v > 0 }),
    market_policy_bias: (v) => ({ label: `Stocks ${v > 0 ? 'boost' : 'hit'}`, positive: v > 0 }),
    welfare_payout: (v) => ({ label: `Welfare ${v > 0 ? '+' : ''}${v}`, positive: v > 0 }),
    treasury_balance: (v) => ({ label: `Treasury $${v}`, positive: v > 0 }),
    player_cash_bonus: (v) => ({ label: `Everyone gets $${v}`, positive: true }),
  };
  for (const [key, value] of Object.entries(effects)) {
    const fn = labels[key];
    if (fn) tags.push(fn(value));
  }
  return tags;
}

export default function GovernmentEventModal() {
  const { governmentEvent, clearGovernmentEvent } = useGameStore();

  if (!governmentEvent) return null;

  const panelClass = CATEGORY_COLORS[governmentEvent.category] || 'border-slate-700/60 bg-slate-950/30';
  const icon = CATEGORY_ICONS[governmentEvent.category] || '📰';
  const effectTags = buildEffectTags(governmentEvent.effects);

  return (
    <div className="modal-overlay">
      <div className={`modal-panel max-w-lg border-2 ${panelClass}`}>
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="flex items-center gap-3">
            <span className="text-3xl">{icon}</span>
            <div>
              <p className="text-[10px] uppercase tracking-[0.28em] text-slate-400">
                Round {governmentEvent.round} · Government Policy
              </p>
              <h2 className="mt-1 text-lg font-bold text-white leading-tight">{governmentEvent.title}</h2>
            </div>
          </div>
          <button onClick={clearGovernmentEvent} className="btn-ghost btn-sm flex-shrink-0">
            Close
          </button>
        </div>

        <p className="text-sm text-slate-300 leading-relaxed">{governmentEvent.description}</p>

        {governmentEvent.plain_text && (
          <div className="mt-4 rounded-xl border border-slate-700 bg-slate-900/60 px-4 py-3">
            <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500 mb-1">In plain terms</p>
            <p className="text-sm font-semibold text-white">{governmentEvent.plain_text}</p>
          </div>
        )}

        {effectTags.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {effectTags.map((tag, i) => (
              <EffectTag key={i} label={tag.label} positive={tag.positive} />
            ))}
          </div>
        )}

        <div className="mt-5">
          <button
            onClick={clearGovernmentEvent}
            className="btn-primary w-full"
          >
            Got it
          </button>
        </div>
      </div>
    </div>
  );
}
