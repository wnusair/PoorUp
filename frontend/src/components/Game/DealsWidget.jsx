import { useMemo } from 'react';
import { useGameStore } from '../../hooks/useGameState';
import { formatRelativeTime } from '../../utils/formatters';
import { getClauseTone, sortDealsForPlayer, summarizeDeal } from '../../utils/deals';

function dealStatusTone(deal, myPlayerId) {
  if (deal.status === 'proposed' && deal.counterparty_id === myPlayerId) {
    return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100';
  }
  if (deal.status === 'accepted') {
    return 'border-cyan-500/30 bg-cyan-500/10 text-cyan-100';
  }
  if (deal.status === 'rejected' || deal.status === 'cancelled' || deal.status === 'expired') {
    return 'border-rose-500/30 bg-rose-500/10 text-rose-100';
  }
  return 'border-slate-700 bg-slate-900/80 text-slate-200';
}


export default function DealsWidget() {
  const { deals, players, properties, myPlayerId, settings, economy, setActiveDeal, setActiveModal, removeQueuedModal } = useGameStore();
  const dealsEnabled = settings?.deals_enabled !== false;

  const items = useMemo(() => sortDealsForPlayer(deals, myPlayerId).slice(0, 3), [deals, myPlayerId]);
  const overflowCount = Math.max(0, sortDealsForPlayer(deals, myPlayerId).length - items.length);

  if (!dealsEnabled) {
    return null;
  }

  return (
    <div className="rounded-xl border border-emerald-900/40 bg-emerald-950/15 p-3 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-emerald-300 uppercase tracking-wider">Deals</h3>
        {overflowCount > 0 && (
          <span className="text-[11px] text-emerald-700">+{overflowCount} more</span>
        )}
      </div>

      {items.length === 0 ? (
        <div className="rounded-lg border border-slate-700 bg-slate-900/80 px-3 py-3 text-xs text-slate-400">
          No active or pending deals.
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((deal) => {
            const summary = summarizeDeal(deal, myPlayerId, players, properties, economy);
            const leadClause = deal.clauses?.[0];
            return (
              <button
                key={deal.id}
                type="button"
                onClick={() => {
                  setActiveDeal(deal);
                  removeQueuedModal('deals', deal.id);
                  setActiveModal('deals');
                }}
                className={`w-full rounded-lg border px-3 py-2 text-left transition hover:border-slate-500 ${dealStatusTone(deal, myPlayerId)}`}
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em]">{summary.title}</p>
                  <span className="text-[11px] text-current/70">
                    {formatRelativeTime(deal.last_updated_at || deal.created_at)}
                  </span>
                </div>
                <p className="mt-1 text-xs leading-5 text-current/90">{summary.body}</p>
                {leadClause && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {deal.clauses.slice(0, 3).map((clause) => (
                      <span
                        key={`${deal.id}-${clause.id}`}
                        className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${getClauseTone(clause.type)}`}
                      >
                        {clause.type === 'rent_immunity' ? 'Immunity' : clause.type === 'rent_discount' ? 'Discount' : 'Investment'}
                      </span>
                    ))}
                  </div>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}