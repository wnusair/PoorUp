import { useGameStore } from '../../hooks/useGameState';
import { formatMoney } from '../../utils/formatters';
import { BOARD_SPACES } from '../../utils/constants';

function DevDots({ level }) {
  if (!level || level === 0) return null;
  const isHotel = level >= 5;
  return (
    <span className="flex items-center gap-0.5 ml-1">
      {isHotel ? (
        <span className="w-2.5 h-2.5 rounded-sm bg-red-400 flex-shrink-0" title="Hotel" />
      ) : (
        Array.from({ length: level }).map((_, i) => (
          <span key={i} className="w-1.5 h-1.5 rounded-full bg-green-400 flex-shrink-0" />
        ))
      )}
    </span>
  );
}

export default function PlayerHUD({ visible }) {
  const { players, myPlayerId, properties } = useGameStore();
  if (!visible) return null;
  const me = players.find((p) => p.id === myPlayerId);
  if (!me) return null;

  const myProperties = Object.entries(properties)
    .filter(([_, p]) => p.owner_id === myPlayerId)
    .map(([pos, p]) => {
      const space = BOARD_SPACES.find((s) => s.position === Number(pos));
      return space ? { pos: Number(pos), name: space.name, color: space.groupColor, ...p } : null;
    })
    .filter(Boolean)
    .sort((a, b) => a.pos - b.pos);

  const isNegative = Number(me.balance || 0) < 0;

  return (
    <div
      className="fixed top-3 right-[19rem] z-40 flex flex-col items-end gap-1.5 pointer-events-none"
      style={{ maxWidth: '220px' }}
    >
      {/* Money badge */}
      <div className={[
        'px-3 py-1.5 rounded-lg border text-sm font-bold font-mono shadow-lg backdrop-blur-sm',
        isNegative
          ? 'bg-red-950/90 border-red-500 text-red-300'
          : 'bg-gray-900/90 border-yellow-500 text-yellow-300',
      ].join(' ')}>
        {formatMoney(me.balance)}
      </div>

      {/* Properties list */}
      {myProperties.length > 0 && (
        <div className="bg-gray-900/85 border border-gray-600 rounded-lg px-2 py-1.5 w-full shadow-lg backdrop-blur-sm space-y-1">
          {myProperties.map((prop) => (
            <div key={prop.pos} className="flex items-center gap-1.5">
              <span
                className="w-2 h-2 rounded-full flex-shrink-0"
                style={{ backgroundColor: prop.color || '#6b7280' }}
              />
              <span className={[
                'text-xs truncate flex-1',
                prop.is_mortgaged ? 'text-gray-500 line-through' : 'text-gray-300',
              ].join(' ')}>
                {prop.name}
              </span>
              {!prop.is_mortgaged && <DevDots level={prop.development_level} />}
              {prop.is_mortgaged && (
                <span className="text-red-400 text-xs flex-shrink-0">M</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
