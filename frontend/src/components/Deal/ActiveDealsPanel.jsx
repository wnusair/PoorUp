import {
  getClauseLabel,
  getClauseTone,
  getDealCounterpartyName,
  sortDealsForPlayer,
  summarizeClause,
} from '../../utils/deals';

export default function ActiveDealsPanel({ deals, players, properties, myPlayerId, selectedDealId, onSelect, economy }) {
  const sortedDeals = sortDealsForPlayer(deals, myPlayerId);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-[0.2em] text-gray-400">Active Deals</h3>
          <p className="mt-1 text-xs text-gray-500">Incoming proposals first, then accepted obligations and protections.</p>
        </div>
        <span className="rounded-full border border-gray-700 bg-gray-900 px-2 py-1 text-[11px] text-gray-400">
          {sortedDeals.length} tracked
        </span>
      </div>

      {sortedDeals.length === 0 ? (
        <div className="rounded-xl border border-gray-700 bg-gray-800/70 p-4 text-sm text-gray-400">
          No deals are active for you right now.
        </div>
      ) : (
        <div className="space-y-2">
          {sortedDeals.map((deal) => (
            <button
              key={deal.id}
              type="button"
              onClick={() => onSelect?.(deal)}
              className={[
                'w-full rounded-xl border p-3 text-left transition',
                selectedDealId === deal.id ? 'border-cyan-500 bg-cyan-950/20' : 'border-gray-700 bg-gray-800/70 hover:border-gray-500',
              ].join(' ')}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-white">{getDealCounterpartyName(deal, myPlayerId, players)}</p>
                  <p className="mt-1 text-xs uppercase tracking-[0.2em] text-gray-500">{deal.status}</p>
                  {deal.status === 'accepted' && deal.termination_requested_by_id && (
                    <p className="mt-2 text-xs text-amber-300">
                      {deal.termination_requested_by_id === myPlayerId
                        ? `Waiting for ${getDealCounterpartyName(deal, myPlayerId, players)} to confirm termination.`
                        : `${deal.termination_requested_by_name || 'The other party'} requested termination.`}
                    </p>
                  )}
                </div>
                <span className="rounded-full border border-gray-700 bg-gray-900 px-2 py-1 text-[11px] text-gray-300">
                  v{deal.proposal_version || 1}
                </span>
              </div>

              <div className="mt-3 flex flex-wrap gap-1.5">
                {deal.clauses.map((clause) => (
                  <span
                    key={`${deal.id}-${clause.id}`}
                    className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${getClauseTone(clause.type)}`}
                  >
                    {getClauseLabel(clause.type)}
                  </span>
                ))}
              </div>

              <div className="mt-3 space-y-2">
                {deal.clauses.slice(0, 2).map((clause) => (
                  <div key={`${deal.id}-${clause.id}-summary`} className="text-xs leading-5 text-gray-300">
                    {summarizeClause(clause, myPlayerId, players, properties, economy)}
                  </div>
                ))}
              </div>

              {deal.clauses.some((clause) => clause.type === 'development_investment') && (
                <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-gray-400">
                  {deal.clauses
                    .filter((clause) => clause.type === 'development_investment')
                    .slice(0, 2)
                    .map((clause) => {
                      const maxPayout = Number(clause?.config?.max_payout || 0);
                      const pairedImmunity = deal.clauses.some((entry) => entry.type === 'rent_immunity');

                      return (
                        <div key={`${deal.id}-${clause.id}-investment`} className="rounded-lg border border-gray-700 bg-gray-900/80 px-2.5 py-2">
                          <p>Unused escrow: ${(Number((clause?.config?.escrow_remaining ?? clause?.config?.escrow_amount) || 0)).toFixed(0)}</p>
                          <p>Paid back: ${(Number(clause?.config?.payout_to_date || 0)).toFixed(0)} / ${maxPayout.toFixed(0)}</p>
                          {pairedImmunity ? (
                            <p className="mt-1 text-[10px] leading-4 text-gray-500">Funded landings still repay this even if a no-rent clause blocks the visitor.</p>
                          ) : null}
                        </div>
                      );
                    })}
                </div>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
