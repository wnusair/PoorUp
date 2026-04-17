import { useEffect, useMemo, useRef } from 'react';
import { useGameStore } from '../../hooks/useGameState';
import { LOG_EVENT_COLORS } from '../../utils/constants';
import { formatTimestamp } from '../../utils/formatters';

const MAX_CENTER_LOG_ENTRIES = 18;

export default function CenterLogDock() {
  const logEntries = useGameStore((state) => state.logEntries);
  const players = useGameStore((state) => state.players);
  const scrollContainerRef = useRef(null);

  const playerMap = useMemo(
    () => Object.fromEntries((players || []).map((player) => [player.id, player])),
    [players],
  );

  const entries = useMemo(
    () => (logEntries || []).slice(-MAX_CENTER_LOG_ENTRIES).map((entry) => ({
      ...entry,
      player: entry.player_id ? playerMap[entry.player_id] : null,
    })),
    [logEntries, playerMap],
  );

  const latestEntryId = entries.at(-1)?.id ?? null;

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) {
      return;
    }

    container.scrollTop = container.scrollHeight;
  }, [latestEntryId]);

  return (
    <div className="pointer-events-auto absolute bottom-[clamp(0.75rem,2vh,1.5rem)] left-1/2 z-10 w-[min(92%,34rem)] -translate-x-1/2">
      <div
        ref={scrollContainerRef}
        aria-label="Recent game events"
        className="max-h-[clamp(7rem,22vh,11rem)] overflow-y-auto pr-2"
      >
        {entries.length === 0 ? (
          <p className="text-xs text-slate-500">No game events yet.</p>
        ) : (
          <div className="space-y-1.5">
            {entries.map((entry) => {
              const colorClass = LOG_EVENT_COLORS[entry.type] || 'text-gray-300';
              return (
                <div key={entry.id} className={`flex items-start gap-2 text-xs drop-shadow-[0_1px_2px_rgba(0,0,0,0.55)] ${colorClass}`}>
                  <span className="w-12 flex-shrink-0 font-mono text-[11px] text-slate-500/90">
                    {formatTimestamp(entry.timestamp)}
                  </span>
                  {entry.player && (
                    <span
                      className="mt-1 h-2 w-2 flex-shrink-0 rounded-full"
                      style={{ backgroundColor: entry.player.color_hex || '#888' }}
                      title={entry.player.username}
                    />
                  )}
                  <span className="min-w-0 flex-1 leading-relaxed text-slate-100/95">{entry.message}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}