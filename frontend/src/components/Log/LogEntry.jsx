import { LOG_EVENT_COLORS, needsDarkText } from '../../utils/constants';
import { formatTimestamp } from '../../utils/formatters';

export default function LogEntry({ entry }) {
  const colorClass = LOG_EVENT_COLORS[entry.type] || 'text-gray-400';
  const player = entry._player; // pre-resolved player object (optional)

  return (
    <div className={`flex items-start gap-1.5 py-0.5 text-xs ${colorClass}`}>
      {/* Timestamp */}
      <span className="text-gray-600 flex-shrink-0 font-mono text-xs w-14">
        {formatTimestamp(entry.timestamp)}
      </span>

      {/* Player colored dot */}
      {player && (
        <div
          className="w-2 h-2 rounded-full flex-shrink-0 mt-1"
          style={{ backgroundColor: player.color_hex || '#666' }}
          title={player.username}
        />
      )}

      {/* Message */}
      <span className="leading-relaxed break-words flex-1">
        {entry.message}
      </span>
    </div>
  );
}
