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
  const committedMembers = Array.isArray(winner?.committed_members) ? winner.committed_members : [];
  const winnerName =
    winner?.type === 'player'
      ? winner.player?.username || `Player ${winner.player?.id}`
      : winner?.type === 'faction'
      ? winner.label || 'People\'s Victory'
      : 'No winner (draw)';

  const winnerColor = winner?.type === 'player'
    ? players.find((p) => p.id === winner.player?.id)?.color_hex
    : winner?.type === 'faction'
    ? '#dc2626'
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
          <p className={`${winner?.type === 'faction' ? 'text-red-300' : 'text-yellow-400'} text-sm font-bold uppercase tracking-widest mb-2`}>
            {winner?.type === 'faction' ? 'Faction Victory' : 'Winner'}
          </p>
          <h2 className="text-3xl font-extrabold text-white">{winnerName}</h2>
          {winner?.type === 'faction' ? (
            <div className="mt-4 rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-100">
              <p className="font-semibold uppercase tracking-[0.22em] text-red-200">Committed Members</p>
              <p className="mt-2 text-base text-white">
                {committedMembers.length > 0
                  ? committedMembers.map((member) => member?.username || `Player ${member?.id}`).join(' • ')
                  : 'No committed members were serialized.'}
              </p>
              <p className="mt-2 text-xs text-red-100/80">
                Control held: {Number(winner?.control_percent || 0).toFixed(1)}% • Round {winner?.victory_round || gameOverData?.round || '?'}
              </p>
            </div>
          ) : null}
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
