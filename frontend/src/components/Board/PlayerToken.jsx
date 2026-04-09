import { needsDarkText } from '../../utils/constants';

export default function PlayerToken({ player, index = 0, size = 'sm', isMoving = false }) {
  if (!player) return null;
  const color = player.color_hex || '#888';
  const textColor = needsDarkText(color) ? '#111' : '#fff';
  const dim = size === 'sm' ? 'w-8 h-8 text-sm' : 'w-10 h-10 text-base';
  const offset = index * 4; // stagger tokens

  return (
    <div
      className={`${dim} rounded-full border-2 flex items-center justify-center font-bold shadow-lg absolute transition-all duration-150`}
      style={{
        backgroundColor: color,
        color: textColor,
        borderColor: isMoving ? '#fff' : 'rgba(255,255,255,0.6)',
        zIndex: 10 + index,
        bottom: `${3 + offset}px`,
        right: `${3 + offset}px`,
        boxShadow: isMoving
          ? `0 0 0 3px rgba(255,255,255,0.9), 0 0 16px 6px ${color}, 0 2px 8px rgba(0,0,0,0.5)`
          : '0 2px 6px rgba(0,0,0,0.4)',
        transform: isMoving ? 'scale(1.15)' : 'scale(1)',
        animation: isMoving ? 'tokenBounce 0.32s ease-in-out infinite alternate' : 'none',
      }}
      title={player.username}
    >
      {player.username?.[0]?.toUpperCase() || '?'}
      {/* Ping ring while moving */}
      {isMoving && (
        <span
          className="absolute inset-0 rounded-full animate-ping"
          style={{ backgroundColor: color, opacity: 0.4 }}
        />
      )}
    </div>
  );
}
