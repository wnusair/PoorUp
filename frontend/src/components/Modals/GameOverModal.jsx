/**
 * GameOverModal — displayed when the game ends. Shows winner and stats.
 */
import { useGameStore } from '../../hooks/useGameState';
import { useNavigate } from 'react-router-dom';
import { formatMoney } from '../../utils/formatters';
import { calculateNetWorth } from '../../utils/formatters';

export default function GameOverModal() {
  const { pendingAction, players, properties, closeModal } = useGameStore();
  const navigate = useNavigate();

  const gameOverData = pendingAction?.data;
  if (!gameOverData) return null;

  const winner = gameOverData.winner;
  const winnerName =
    winner?.type === 'player'
      ? winner.player?.username || `Player ${winner.player?.id}`
      : 'No winner (draw)';

  const winnerColor =
    winner?.type === 'player'
      ? players.find(p => p.id === winner.player?.id)?.color_hex
      : null;

  // Sort players by net worth descending
  const ranked = [...players]
    .map(p => ({
      ...p,
      netWorth: calculateNetWorth(p, properties),
    }))
    .sort((a, b) => b.netWorth - a.netWorth);

  function handleBackToHome() {
    navigate('/');
    closeModal();
    window.location.reload();
  }

  return (
    <div className="modal-overlay">
      <div className="modal-panel modal-panel--wide">
        {/* Winner announcement */}
        <div className="text-center mb-8">
          {winnerColor && (
            <div
              className="w-16 h-16 rounded-full mx-auto mb-4 border-4 border-white/20 shadow-lg"
              style={{ backgroundColor: winnerColor }}
            />
          )}
          <p className="text-yellow-400 text-sm font-bold uppercase tracking-widest mb-2">
            Winner
          </p>
          <h2 className="text-3xl font-extrabold text-white">{winnerName}</h2>
          {gameOverData.reason === 'host_ended' && (
            <p className="text-gray-400 text-sm mt-2">Game ended by host.</p>
          )}
        </div>

        {/* Final standings */}
        <div className="mb-6">
          <h3 className="text-xs uppercase tracking-wide text-gray-500 mb-3">Final Standings</h3>
          <div className="space-y-2">
            {ranked.map((p, i) => (
              <div
                key={p.id}
                className="flex items-center gap-3 bg-gray-800 rounded-lg px-4 py-2"
              >
                <span className="text-gray-500 font-bold w-5 text-right">{i + 1}.</span>
                <div
                  className="w-3 h-3 rounded-full flex-shrink-0"
                  style={{ backgroundColor: p.color_hex }}
                />
                <span className={`flex-1 font-semibold ${p.is_bankrupt ? 'line-through text-gray-500' : 'text-white'}`}>
                  {p.username}
                </span>
                {p.is_bankrupt ? (
                  <span className="text-red-500 text-xs font-bold">BANKRUPT</span>
                ) : (
                  <span className="text-green-300 font-mono text-sm">{formatMoney(p.netWorth)}</span>
                )}
              </div>
            ))}
          </div>
        </div>

        <button onClick={handleBackToHome} className="btn-primary w-full text-base py-3">
          Back to Home
        </button>
      </div>
    </div>
  );
}
