import { useEffect, useRef, useState } from 'react';
import { useGameStore } from '../../hooks/useGameState';
import LogEntry from './LogEntry';
import { LOG_EVENT_COLORS } from '../../utils/constants';

const EVENT_TYPE_GROUPS = [
  { label: 'Movement', types: ['dice_roll', 'move', 'turn_timeout'] },
  { label: 'Finance', types: ['rent_collected', 'income_tax', 'luxury_tax', 'super_tax', 'turn_tax', 'property_tax', 'welfare_paid', 'welfare_failed'] },
  { label: 'Property', types: ['property_purchased', 'auction_won'] },
  { label: 'Social', types: ['trade_proposed', 'trade_completed', 'trade_rejected', 'deal_proposed', 'deal_countered', 'deal_accepted', 'deal_rejected', 'deal_cancelled', 'deal_termination_requested', 'deal_expired', 'deal_immunity_applied', 'deal_discount_applied', 'deal_investment_spent', 'deal_profit_paid', 'lobby_pending', 'lobby_success', 'lobby_failed'] },
  { label: 'Events', types: ['uprising', 'hyper_inflation', 'bankruptcy', 'chance_card', 'community_chest', 'jail_sent', 'jail_released'] },
];

const ALL_TYPES = EVENT_TYPE_GROUPS.flatMap((g) => g.types);

export default function GameLog() {
  const { logEntries, players } = useGameStore();
  const bottomRef = useRef(null);
  const [activeFilters, setActiveFilters] = useState(new Set(ALL_TYPES));
  const [showFilters, setShowFilters] = useState(false);

  const playerMap = Object.fromEntries(players.map((p) => [p.id, p]));

  const filtered = logEntries
    .filter((e) => activeFilters.has(e.type))
    .map((e) => ({
      ...e,
      _player: e.player_id ? playerMap[e.player_id] : null,
    }));

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logEntries.length]);

  const toggleFilter = (type) => {
    setActiveFilters((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  const toggleGroup = (types) => {
    setActiveFilters((prev) => {
      const next = new Set(prev);
      const allOn = types.every((t) => next.has(t));
      types.forEach((t) => (allOn ? next.delete(t) : next.add(t)));
      return next;
    });
  };

  const handleDownload = () => {
    const text = logEntries
      .map((e) => `[${e.timestamp || ''}] ${e.message}`)
      .join('\n');
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'poorup-game-log.txt';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col h-full bg-gray-900">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-gray-700 flex-shrink-0">
        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
          Game Log ({logEntries.length})
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowFilters((v) => !v)}
            className="text-xs text-gray-500 hover:text-gray-300 transition"
          >
            Filter
          </button>
          <button
            onClick={handleDownload}
            className="text-xs text-gray-500 hover:text-gray-300 transition"
          >
            ↓ .txt
          </button>
        </div>
      </div>

      {/* Filter panel */}
      {showFilters && (
        <div className="px-3 py-2 border-b border-gray-700 bg-gray-850 flex-shrink-0">
          <div className="flex flex-wrap gap-2">
            {EVENT_TYPE_GROUPS.map((group) => {
              const allOn = group.types.every((t) => activeFilters.has(t));
              return (
                <button
                  key={group.label}
                  onClick={() => toggleGroup(group.types)}
                  className={[
                    'text-xs px-2 py-0.5 rounded border transition',
                    allOn
                      ? 'bg-blue-800 border-blue-600 text-white'
                      : 'bg-gray-800 border-gray-600 text-gray-400',
                  ].join(' ')}
                >
                  {group.label}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Log content */}
      <div className="flex-1 overflow-y-auto px-3 py-1 space-y-0.5">
        {filtered.length === 0 && (
          <p className="text-xs text-gray-600 italic text-center mt-4">No events to display.</p>
        )}
        {filtered.map((entry) => (
          <LogEntry key={entry.id} entry={entry} />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
