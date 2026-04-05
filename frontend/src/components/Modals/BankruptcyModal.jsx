/**
 * BankruptcyModal — announces a player's bankruptcy.
 */
import { useGameStore } from '../../hooks/useGameState';

export default function BankruptcyModal({ data = null, onClose }) {
  const { pendingAction, closeModal, players } = useGameStore();

  const bankruptcyData = data || pendingAction?.data || {};
  const handleClose = onClose || closeModal;

  const bankruptPlayerId = bankruptcyData?.player_id;
  const bankruptPlayer = players.find((player) => player.id === bankruptPlayerId);

  if (!bankruptPlayer) return null;

  let detailText = 'Their holdings have been returned to the bank.';
  if (bankruptcyData?.resolution_type === 'asset_liquidation') {
    detailText = `Asset liquidation covered $${Number(bankruptcyData?.debt_paid || 0).toFixed(2)} before they were removed.`;
  } else if (bankruptcyData?.resolution_type === 'government_reimbursement') {
    detailText = `The government reimbursed $${Number(bankruptcyData?.reimbursed_amount || 0).toFixed(2)} before they were removed from play.`;
  }

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div
        className="modal-panel max-w-sm text-center"
        onClick={(event) => event.stopPropagation()}
      >
        {/* Color indicator */}
        <div
          className="w-12 h-12 rounded-full mx-auto mb-4 border-4 border-gray-700 opacity-50"
          style={{ backgroundColor: bankruptPlayer.color_hex }}
        />

        <h2 className="text-2xl font-extrabold text-red-500 mb-2">BANKRUPT</h2>
        <p className="text-white font-semibold text-lg mb-1">{bankruptPlayer.username}</p>
        <p className="text-gray-400 text-sm mb-6">
          has been eliminated from the game. {detailText}
        </p>

        <button onClick={handleClose} className="btn-ghost w-full">
          Continue
        </button>
      </div>
    </div>
  );
}
