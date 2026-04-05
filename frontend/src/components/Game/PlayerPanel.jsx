import { useState } from 'react';
import { useGameStore } from '../../hooks/useGameState';
import { formatMoney } from '../../utils/formatters';
import { needsDarkText, BOARD_SPACES } from '../../utils/constants';

function PropertyTag({ position, properties }) {
  const prop = properties[position];
  const space = BOARD_SPACES.find((s) => s.position === position);
  if (!space) return null;

  return (
    <div
      className="flex items-center gap-1 px-1.5 py-0.5 rounded text-xs"
      style={{
        backgroundColor: space.groupColor ? `${space.groupColor}33` : '#374151',
        borderLeft: `3px solid ${space.groupColor || '#6b7280'}`,
      }}
    >
      <span className="text-gray-300 truncate max-w-[6rem]">{space.name}</span>
      {prop?.is_mortgaged && (
        <span className="text-red-400 text-xs">M</span>
      )}
      {prop?.development_level > 0 && (
        <span className="text-green-400 text-xs">D{prop.development_level}</span>
      )}
    </div>
  );
}

function PlayerRow({ player, isMe, isCurrent, properties, deals, isHost }) {
  const [expanded, setExpanded] = useState(false);
  const color = player.color_hex || '#888';
  const textColor = needsDarkText(color) ? '#111' : '#fff';

  const playerDeals = (deals || []).filter(
    (deal) => deal.proposer_id === player.id || deal.counterparty_id === player.id,
  );
  const activeDealCount = playerDeals.filter((deal) => deal.status === 'accepted').length;
  const pendingIncomingCount = playerDeals.filter((deal) => deal.status === 'proposed' && deal.counterparty_id === player.id).length;

  const ownedPositions = Object.entries(properties)
    .filter(([_, p]) => p.owner_id === player.id)
    .map(([pos]) => Number(pos));

  return (
    <div
      className={[
        'rounded-lg border transition',
        isCurrent ? 'border-yellow-400 bg-gray-700' : isMe ? 'border-blue-600 bg-gray-750' : 'border-gray-700 bg-gray-800',
        player.bankrupt ? 'opacity-40' : '',
      ].join(' ')}
    >
      <button
        className="w-full flex items-center gap-2 p-2.5 text-left"
        onClick={() => setExpanded((v) => !v)}
      >
        {/* Color dot */}
        <div
          className="w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold shadow"
          style={{ backgroundColor: color, color: textColor }}
        >
          {player.username?.[0]?.toUpperCase()}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-white text-sm font-medium truncate">{player.username}</span>
            {isMe && <span className="text-xs bg-blue-700 text-white px-1 rounded">You</span>}
            {isHost && <span className="text-xs bg-yellow-700 text-white px-1 rounded">Host</span>}
            {isCurrent && (
              <span className="text-xs bg-yellow-500 text-black px-1 rounded animate-pulse font-bold">
                TURN
              </span>
            )}
            {player.bankrupt && (
              <span className="text-xs bg-red-900 text-red-300 px-1 rounded">BANKRUPT</span>
            )}
            {player.in_jail && (
              <span className="text-xs bg-orange-900 text-orange-300 px-1 rounded">JAIL</span>
            )}
            {activeDealCount > 0 && (
              <span className="text-xs rounded bg-cyan-900 px-1 text-cyan-200">{activeDealCount} deal{activeDealCount === 1 ? '' : 's'}</span>
            )}
            {pendingIncomingCount > 0 && (
              <span className="text-xs rounded bg-emerald-900 px-1 text-emerald-200">{pendingIncomingCount} incoming</span>
            )}
          </div>
          <div className="text-xs text-gray-400 font-mono">
            <span className={Number(player.balance || 0) < 0 ? 'text-red-400' : 'text-gray-400'}>
              {formatMoney(player.balance)}
            </span>
          </div>
        </div>

        <div className="text-gray-500 text-xs ml-1">
          {expanded ? '▲' : '▼'}
        </div>
      </button>

      {expanded && (
        <div className="px-2.5 pb-2.5 space-y-2 border-t border-gray-700 pt-2">
          <div className="text-xs text-gray-500">
            Properties ({ownedPositions.length})
          </div>
          {ownedPositions.length > 0 ? (
            <div className="flex flex-wrap gap-1">
              {ownedPositions.map((pos) => (
                <PropertyTag key={pos} position={pos} properties={properties} />
              ))}
            </div>
          ) : (
            <p className="text-xs text-gray-600 italic">No properties</p>
          )}
        </div>
      )}
    </div>
  );
}

export default function PlayerPanel({ lobbyData }) {
  const { players, currentPlayerId, myPlayerId, properties, deals } = useGameStore();
  const hostId = lobbyData?.host_id;

  return (
    <div className="space-y-2 overflow-y-auto">
      {players.map((player) => (
        <PlayerRow
          key={player.id}
          player={player}
          isMe={player.id === myPlayerId}
          isCurrent={player.id === currentPlayerId}
          isHost={player.id === hostId}
          properties={properties}
          deals={deals}
        />
      ))}
    </div>
  );
}
