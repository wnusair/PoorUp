import { useGameStore } from '../../hooks/useGameState';

export default function TradeFeed() {
  const { logEntries, players } = useGameStore();

  const tradeEvents = logEntries
    .filter((e) => ['trade_proposed', 'trade_completed', 'trade_rejected'].includes(e.type))
    .slice(-3)
    .reverse();

  if (tradeEvents.length === 0) return null;

  const playerMap = Object.fromEntries(players.map((p) => [p.id, p]));

  const colors = {
    trade_proposed: 'border-yellow-700 bg-yellow-950/40',
    trade_completed: 'border-green-700 bg-green-950/40',
    trade_rejected: 'border-gray-700 bg-gray-850',
  };

  const labels = {
    trade_proposed: 'Proposed',
    trade_completed: 'Completed',
    trade_rejected: 'Rejected',
  };

  return (
    <div className="px-3 py-1.5 flex gap-2 overflow-x-auto flex-shrink-0 border-b border-gray-700 bg-gray-900">
      {tradeEvents.map((entry) => {
        const player = entry.player_id ? playerMap[entry.player_id] : null;
        return (
          <div
            key={entry.id}
            className={`flex-shrink-0 flex items-center gap-2 px-3 py-1 rounded-full border text-xs ${colors[entry.type]}`}
          >
            {player && (
              <div
                className="w-2 h-2 rounded-full flex-shrink-0"
                style={{ backgroundColor: player.color_hex || '#888' }}
              />
            )}
            <span className="text-gray-400">{labels[entry.type]}</span>
            <span className="text-gray-300 truncate max-w-xs">{entry.message}</span>
          </div>
        );
      })}
    </div>
  );
}
