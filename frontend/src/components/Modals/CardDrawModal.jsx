/**
 * CardDrawModal — animated card reveal for Chance and Community Chest.
 */
import { useState, useEffect } from 'react';
import { useGameStore } from '../../hooks/useGameState';

const DECK_COLORS = {
  chance: { bg: 'bg-yellow-400', text: 'text-yellow-900', label: 'CHANCE' },
  community_chest: { bg: 'bg-blue-500', text: 'text-white', label: 'COMMUNITY CHEST' },
};

export default function CardDrawModal() {
  const { pendingAction, closeModal } = useGameStore();
  const [flipped, setFlipped] = useState(false);

  const cardData = pendingAction?.data;
  const deckType = cardData?.card_type || cardData?.type || 'chance';
  const card = cardData?.card;
  const colors = DECK_COLORS[deckType] || DECK_COLORS.chance;

  // Auto-flip after brief pause
  useEffect(() => {
    const t = setTimeout(() => setFlipped(true), 300);
    return () => clearTimeout(t);
  }, []);

  // Auto-close after 4 seconds
  useEffect(() => {
    if (!flipped) return;
    const t = setTimeout(() => closeModal(), 4000);
    return () => clearTimeout(t);
  }, [flipped, closeModal]);

  if (!card) return null;

  return (
    <div className="modal-overlay" onClick={closeModal}>
      <div
        className="modal-panel max-w-sm text-center cursor-pointer"
        onClick={e => { e.stopPropagation(); closeModal(); }}
        style={{ perspective: '1000px' }}
      >
        <div
          className="relative w-full transition-transform duration-700"
          style={{
            transformStyle: 'preserve-3d',
            transform: flipped ? 'rotateY(0deg)' : 'rotateY(90deg)',
          }}
        >
          {/* Card type badge */}
          <div className={`inline-block ${colors.bg} ${colors.text} text-xs font-bold px-3 py-1 rounded-full mb-4 tracking-widest`}>
            {colors.label}
          </div>

          {/* Card text */}
          <p className="text-white text-lg font-semibold mb-6 leading-snug">
            "{card.card_text}"
          </p>

          {/* Effect highlight */}
          <div className="bg-gray-800 rounded-lg p-3 text-sm text-gray-300">
            {getEffectDescription(card)}
          </div>
        </div>

        <p className="text-gray-600 text-xs mt-6">Click to dismiss</p>
      </div>
    </div>
  );
}

function getEffectDescription(card) {
  const { effect_type, effect_value } = card;
  switch (effect_type) {
    case 'collect': return `Collect $${effect_value}`;
    case 'pay': return `Pay $${effect_value}`;
    case 'advance_to_start': return 'Move to START and collect GO salary';
    case 'advance_to_position': return `Move to board position ${effect_value}`;
    case 'advance_to_nearest_transit': return 'Move to nearest airport';
    case 'go_to_jail': return 'Go directly to Jail';
    case 'get_out_of_jail_free': return 'Keep this card — use to escape jail for free';
    case 'move_back': return `Move back ${effect_value} spaces`;
    case 'street_repairs': return `Pay $25 per building, $100 per hotel`;
    case 'street_repairs_community': return `Pay $40 per building, $115 per hotel`;
    case 'collect_from_each_player': return `Collect $${effect_value} from each player`;
    case 'pay_each_player': return `Pay $${effect_value} to each player`;
    case 'collect_welfare_bonus': return 'Collect current welfare payout × 2';
    default: return effect_type;
  }
}
