import { useGameStore } from '../../hooks/useGameState';
import { formatMoney } from '../../utils/formatters';
import { needsDarkText } from '../../utils/constants';

function calcNetWorth(player, properties) {
  let worth = player.balance || 0;
  Object.values(properties).forEach((prop) => {
    if (prop.owner_id === player.id) {
      const base = prop.price || 0;
      const devBonus = (prop.development_level || 0) * (base * 0.5);
      const mortgagePenalty = prop.is_mortgaged ? base * 0.5 : 0;
      worth += base + devBonus - mortgagePenalty;
    }
  });
  return worth;
}

export default function Leaderboard() {
  const { players, properties, myPlayerId } = useGameStore();

  const ranked = [...players]
    .filter((p) => !p.bankrupt)
    .map((p) => ({ ...p, netWorth: calcNetWorth(p, properties) }))
    .sort((a, b) => b.netWorth - a.netWorth);

  const bankrupt = players.filter((p) => p.bankrupt);

  return (
    <div className="bg-gray-800 rounded-xl p-3">
      <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
        Leaderboard
      </h3>
      <div className="space-y-2">
        {ranked.map((player, i) => {
          const isMe = player.id === myPlayerId;
          const textColor = needsDarkText(player.color_hex) ? '#111' : '#fff';
          return (
            <div
              key={player.id}
              className={[
                'flex items-center gap-2 p-2 rounded-lg text-sm',
                isMe ? 'bg-gray-700 border border-gray-500' : 'bg-gray-750',
              ].join(' ')}
            >
              <span className="text-gray-500 w-4 text-center font-mono text-xs">
                {`${i + 1}.`}
              </span>
              <div
                className="w-5 h-5 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold"
                style={{ backgroundColor: player.color_hex || '#555', color: textColor }}
              >
                {player.username?.[0]?.toUpperCase()}
              </div>
              <span className="flex-1 text-gray-200 truncate text-xs">{player.username}</span>
              <span className="text-yellow-400 font-mono text-xs font-bold">
                {formatMoney(player.netWorth)}
              </span>
            </div>
          );
        })}
        {bankrupt.map((player) => (
          <div
            key={player.id}
            className="flex items-center gap-2 p-2 rounded-lg text-sm opacity-40"
          >
            <span className="text-gray-600 w-4 text-center text-xs">-</span>
            <div
              className="w-5 h-5 rounded-full flex-shrink-0"
              style={{ backgroundColor: player.color_hex || '#555' }}
            />
            <span className="flex-1 text-gray-500 truncate text-xs line-through">
              {player.username}
            </span>
            <span className="text-red-800 text-xs">BANKRUPT</span>
          </div>
        ))}
      </div>
    </div>
  );
}
