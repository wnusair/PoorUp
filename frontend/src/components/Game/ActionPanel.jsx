import { useGameStore } from '../../hooks/useGameState';
import DiceDisplay from './DiceDisplay';
import TurnTimer from './TurnTimer';
import { formatMoney } from '../../utils/formatters';
import { numberValue } from '../../utils/economy';

export default function ActionPanel({
  onRoll,
  onEndTurn,
  onPayJail,
  onJailCard,
  onDeclareBankruptcy,
}) {
  const {
    isMyTurn,
    diceResult,
    diceRolledThisTurn,
    isRolling,
    players,
    myPlayerId,
    pendingDebts,
    settings,
    economy,
    pendingAction,
    activeModal,
    movingPlayerId,
    awaitingEndTurnPlayerId,
    setActiveModal,
  } = useGameStore();

  const myTurn = isMyTurn();
  const me = players.find((p) => p.id === myPlayerId);
  const hasRolled = diceRolledThisTurn;
  const inJail = me?.in_jail;
  const hasJailCard = me?.jail_cards > 0;
  const myDebtEntries = pendingDebts.filter((entry) => entry.debtor_id === myPlayerId);
  const totalDebt = myDebtEntries.reduce((sum, entry) => sum + Number(entry.amount_due || 0), 0);
  const primaryDebt = myDebtEntries[0] || null;
  const primaryCreditor = primaryDebt
    ? players.find((player) => player.id === primaryDebt.creditor_id)
    : null;
  const isInDebt = Number(me?.balance || 0) < 0 || myDebtEntries.length > 0;
  const govType = settings?.government_type || 'liberal_democracy';
  const treasuryBalance = numberValue(economy?.treasury_balance, 0);
  const bailoutEnabled = govType !== 'minarchism' && Boolean(economy?.bailout_enabled);
  const bailoutAmount = Math.max(0, -numberValue(me?.balance, 0)) + 200;
  const bailoutAvailable = bailoutEnabled && treasuryBalance >= bailoutAmount;

  const propertyPrompt = pendingAction?.type === 'buy_property' && pendingAction?.data?.player_id === myPlayerId;
  const turnResolutionModalOpen = ['property', 'card', 'auction', 'bankruptcy', 'game_over'].includes(activeModal);
  const canEndTurn = myTurn
    && awaitingEndTurnPlayerId === myPlayerId
    && !isInDebt
    && !propertyPrompt
    && movingPlayerId == null
    && !turnResolutionModalOpen;

  return (
    <div className="space-y-4">
      {/* Timer */}
      <TurnTimer />

      {/* Dice */}
      <div className="flex flex-col items-center gap-3">
        <DiceDisplay />

        {myTurn && !hasRolled && !isRolling && (
          <div className="space-y-2 w-full">
            {inJail ? (
              <div className="space-y-2">
                <p className="text-orange-400 text-sm text-center font-medium">
                  You're in Jail!
                </p>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={onPayJail}
                    className="py-2 px-3 bg-orange-700 hover:bg-orange-600 text-white text-sm rounded-lg font-medium transition"
                  >
                    Pay $50 Bail
                  </button>
                  {hasJailCard && (
                    <button
                      onClick={onJailCard}
                      className="py-2 px-3 bg-purple-700 hover:bg-purple-600 text-white text-sm rounded-lg font-medium transition"
                    >
                      Use Get Out Card
                    </button>
                  )}
                </div>
                <button
                  onClick={onRoll}
                  className="w-full py-3 bg-yellow-600 hover:bg-yellow-500 text-white font-bold text-lg rounded-xl shadow-lg transition"
                >
                  Try for Doubles
                </button>
              </div>
            ) : (
              <button
                onClick={onRoll}
                className="w-full py-3 bg-blue-600 hover:bg-blue-500 text-white font-bold text-xl rounded-xl shadow-lg
                           hover:shadow-blue-500/30 transition active:scale-95"
              >
                Roll Dice
              </button>
            )}
          </div>
        )}

        {myTurn && hasRolled && propertyPrompt && (
          <button
            onClick={() => setActiveModal('property')}
            className="w-full py-2 px-3 bg-green-800 hover:bg-green-700 text-white text-sm rounded-lg font-medium transition"
          >
            Resolve {pendingAction?.data?.property?.name || 'property'}
          </button>
        )}

        {myTurn && isInDebt && (
          <div className="w-full rounded-xl border border-red-500/70 bg-red-950/70 p-4 space-y-3 shadow-lg shadow-red-950/40">
            <div className="text-center space-y-1">
              <p className="text-red-200 font-bold tracking-wide">Negative Balance</p>
              <p className="text-2xl font-extrabold text-red-400">{formatMoney(me?.balance || 0)}</p>
              <p className="text-xs text-red-100/80">
                {totalDebt > 0
                  ? `You still owe ${formatMoney(totalDebt)} to ${primaryCreditor?.username || primaryDebt?.creditor_name || 'another player'}.`
                  : 'You cannot end your turn until your balance is positive again.'}
              </p>
              {bailoutEnabled && (
                <p className="text-xs text-red-100/70">
                  {bailoutAvailable
                    ? `Treasury rescue available. Requesting it will draw ${formatMoney(bailoutAmount)} from the bank.`
                    : 'Bailouts are enabled, but the treasury cannot cover a rescue right now.'}
                </p>
              )}
              {primaryDebt?.property_name && (
                <p className="text-xs text-red-100/70">
                  Debt source: {primaryDebt.property_name}
                </p>
              )}
            </div>
            <button
              onClick={onDeclareBankruptcy}
              className="w-full py-3 bg-red-700 hover:bg-red-600 text-white font-bold text-sm rounded-xl transition"
            >
              {bailoutAvailable ? 'REQUEST BAILOUT' : 'DECLARE BANKRUPTCY'}
            </button>
          </div>
        )}

        {canEndTurn && (
          <div className="space-y-2 w-full">
            <button
              onClick={onEndTurn}
              className="w-full py-3 bg-emerald-700 hover:bg-emerald-600 text-white font-bold text-lg rounded-xl shadow-lg transition"
            >
              End Turn
            </button>
          </div>
        )}

        {myTurn && hasRolled && !propertyPrompt && !canEndTurn && !isInDebt && (
          <p className="text-green-400 text-sm text-center">
            Dice rolled — turn resolving…
          </p>
        )}

        {!myTurn && (
          <p className="text-gray-500 text-sm text-center italic">
            Waiting for other player…
          </p>
        )}
      </div>
    </div>
  );
}
