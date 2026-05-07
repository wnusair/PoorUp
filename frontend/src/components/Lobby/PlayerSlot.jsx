import { needsDarkText } from '../../utils/constants';

export default function PlayerSlot({ player, isMe, isHost, slotIndex, canRemoveBot = false, onRemoveBot }) {
  if (!player) {
    return (
      <div className="flex items-center gap-3 p-3 bg-gray-800 border border-dashed border-gray-600 rounded-lg opacity-50">
        <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center text-gray-500 text-xs">
          {slotIndex + 1}
        </div>
        <span className="text-gray-500 text-sm italic">Waiting for player…</span>
      </div>
    );
  }

  const textColor = needsDarkText(player.color_hex) ? '#111' : '#fff';
  const difficultyTone = {
    easy: 'border-emerald-700/70 bg-emerald-950/40 text-emerald-200',
    normal: 'border-sky-700/70 bg-sky-950/40 text-sky-200',
    hard: 'border-amber-700/70 bg-amber-950/40 text-amber-200',
    expert: 'border-rose-700/70 bg-rose-950/40 text-rose-200',
  }[player.bot_difficulty] || 'border-gray-700 bg-gray-900 text-gray-200';

  return (
    <div
      className={[
        'flex items-center gap-3 p-3 rounded-lg border transition',
        isMe ? 'border-white bg-gray-700' : 'border-gray-600 bg-gray-800',
      ].join(' ')}
    >
      {/* Color dot */}
      <div
        className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shadow"
        style={{ backgroundColor: player.color_hex || '#555', color: textColor }}
      >
        {player.username?.[0]?.toUpperCase() || '?'}
      </div>

      {/* Name + badges */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-white font-medium truncate">{player.username}</span>
          {isMe && (
            <span className="text-xs bg-blue-600 text-white px-1.5 py-0.5 rounded">You</span>
          )}
          {isHost && (
            <span className="text-xs bg-yellow-600 text-white px-1.5 py-0.5 rounded">Host</span>
          )}
          {player.is_bot && (
            <span className="text-xs bg-indigo-600 text-white px-1.5 py-0.5 rounded">Bot</span>
          )}
        </div>
        {player.is_bot && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-wide ${difficultyTone}`}>
              {player.bot_difficulty_label || player.bot_difficulty}
            </span>
            <span className="rounded-full border border-indigo-900/70 bg-indigo-950/30 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-indigo-200">
              {player.bot_archetype_label || player.bot_archetype || player.bot_persona_label || player.bot_persona}
            </span>
          </div>
        )}
        {player.is_bot && (player.bot_archetype_description || player.bot_persona_description) && (
          <p className="mt-2 text-xs text-gray-400 truncate">{player.bot_archetype_description || player.bot_persona_description}</p>
        )}
      </div>

      {/* Ready status */}
      <div className="flex items-center gap-2">
        <div className={['text-sm font-semibold', player.is_ready ? 'text-green-400' : 'text-gray-500'].join(' ')}>
          {player.is_ready ? 'Ready' : 'Not Ready'}
        </div>
        {canRemoveBot && (
          <button
            onClick={onRemoveBot}
            className="rounded bg-red-700 px-2 py-1 text-xs font-semibold text-white transition hover:bg-red-600"
          >
            Remove
          </button>
        )}
      </div>
    </div>
  );
}
