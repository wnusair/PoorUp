import { useMemo } from 'react';
import { useGameStore } from '../../hooks/useGameState';
import { formatMoney, formatRelativeTime } from '../../utils/formatters';

function statusTone(kind) {
  if (kind === 'incoming') {
    return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100';
  }
  if (kind === 'outgoing') {
    return 'border-cyan-500/30 bg-cyan-500/10 text-cyan-100';
  }
  if (kind === 'completed') {
    return 'border-slate-700 bg-slate-900/80 text-slate-200';
  }
  if (kind === 'rejected') {
    return 'border-rose-500/30 bg-rose-500/10 text-rose-100';
  }
  return 'border-amber-500/30 bg-amber-500/10 text-amber-100';
}

function tradeSummary(trade) {
  const offeredMoney = Number(trade?.offer_money || 0);
  const requestedMoney = Number(trade?.request_money || 0);
  const offerPropertyCount = Array.isArray(trade?.offer_properties) ? trade.offer_properties.length : 0;
  const requestPropertyCount = Array.isArray(trade?.request_properties) ? trade.request_properties.length : 0;
  const includedDealDraftCount = Array.isArray(trade?.included_deal_drafts) ? trade.included_deal_drafts.length : 0;

  const parts = [];
  if (offeredMoney > 0) {
    parts.push(`Offers ${formatMoney(offeredMoney)}`);
  }
  if (offerPropertyCount > 0) {
    parts.push(`${offerPropertyCount} property${offerPropertyCount === 1 ? '' : 'ies'} offered`);
  }
  if (requestedMoney > 0) {
    parts.push(`Asks ${formatMoney(requestedMoney)}`);
  }
  if (requestPropertyCount > 0) {
    parts.push(`${requestPropertyCount} property${requestPropertyCount === 1 ? '' : 'ies'} requested`);
  }
  if (includedDealDraftCount > 0) {
    parts.push(`${includedDealDraftCount} bundled deal draft${includedDealDraftCount === 1 ? '' : 's'}`);
  }

  return parts.length > 0 ? parts.join(' • ') : 'Open trade proposal';
}

export default function TradeQueueWidget() {
  const { trades, logEntries, myPlayerId, settings, setActiveModal, setActiveTrade, removeQueuedModal, clearTrade } = useGameStore();
  const tradingEnabled = settings?.trading_enabled !== false;

  const items = useMemo(() => {
    const nextItems = [];

    const pendingTrades = (trades || []).slice(0, 3);
    for (const trade of pendingTrades) {
      const incoming = trade.receiver_id === myPlayerId;
      nextItems.push({
        key: `trade-${trade.id || `${trade.proposer_id}-${trade.receiver_id}`}`,
        kind: incoming ? 'incoming' : 'outgoing',
        title: incoming
          ? `Incoming from ${trade.proposer_name || 'Player'}`
          : `Pending with ${trade.receiver_name || 'Player'}`,
        body: tradeSummary(trade),
        timestamp: trade.created_at,
        trade,
      });
    }

    const recentLogItems = (logEntries || [])
      .filter((entry) => ['trade_proposed', 'trade_completed', 'trade_rejected'].includes(entry.type))
      .slice(-6)
      .reverse()
      .map((entry) => ({
        key: entry.id,
        kind: entry.type === 'trade_completed' ? 'completed' : entry.type === 'trade_rejected' ? 'rejected' : 'proposed',
        title: entry.type === 'trade_completed' ? 'Trade completed' : entry.type === 'trade_rejected' ? 'Trade rejected' : 'Trade proposed',
        body: entry.message,
        timestamp: entry.timestamp,
      }));

    for (const item of recentLogItems) {
      if (nextItems.length >= 3) {
        break;
      }
      if (!nextItems.some((existing) => existing.body === item.body && existing.kind === item.kind)) {
        nextItems.push(item);
      }
    }

    return nextItems;
  }, [logEntries, myPlayerId, trades]);

  const overflowCount = Math.max(0, (trades || []).length - items.filter((item) => item.trade).length);

  if (!tradingEnabled) {
    return null;
  }

  return (
    <div className="rounded-xl border border-cyan-900/40 bg-cyan-950/15 p-3 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-cyan-300 uppercase tracking-wider">Trade Queue</h3>
        {overflowCount > 0 && (
          <span className="text-[11px] text-cyan-700">+{overflowCount} more</span>
        )}
      </div>

      {items.length === 0 ? (
        <div className="rounded-lg border border-slate-700 bg-slate-900/80 px-3 py-3 text-xs text-slate-400">
          No active or recent trades.
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => {
                if (item.trade) {
                  setActiveTrade(item.trade);
                  removeQueuedModal('trade', item.trade.id);
                } else {
                  clearTrade();
                }
                setActiveModal('trade');
              }}
              className={`w-full rounded-lg border px-3 py-2 text-left transition hover:border-slate-500 ${statusTone(item.kind)}`}
            >
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-semibold uppercase tracking-[0.18em]">{item.title}</p>
                {item.timestamp && (
                  <span className="text-[11px] text-slate-400">{formatRelativeTime(item.timestamp)}</span>
                )}
              </div>
              <p className="mt-1 text-xs leading-5 text-current/90">{item.body}</p>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}