/**
 * AuctionModal — real-time bidding on an unowned property.
 * Timer resets to 5s on each new bid and closes automatically when it expires.
 */
import { useState, useEffect } from 'react';
import { useGameStore } from '../../hooks/useGameState';
import { getSocket } from '../../hooks/useSocket';
import { formatMoney } from '../../utils/formatters';

const AUCTION_COUNTDOWN_SECONDS = 5;
const BID_INCREMENTS = [1, 10, 100];


export default function AuctionModal() {
  const { auctionState, myPlayerId, matchId, players } = useGameStore();
  const [timeLeft, setTimeLeft] = useState(AUCTION_COUNTDOWN_SECONDS);
  const [timerResetKey, setTimerResetKey] = useState(0);
  const [error, setError] = useState('');

  const property = auctionState?.property;
  const bids = auctionState?.bids || [];
  const highestBid = auctionState?.highestBid || 0;
  const highestBidderId = auctionState?.highestBidderId;
  const highestBidder = players.find(p => p.id === highestBidderId);

  useEffect(() => {
    if (!auctionState?.active) return;
    setTimeLeft(auctionState.timeLeft || AUCTION_COUNTDOWN_SECONDS);
    setTimerResetKey((value) => value + 1);
  }, [auctionState?.active, auctionState?.timeLeft, property?.id, highestBid, bids.length]);

  useEffect(() => {
    if (!auctionState?.active || timeLeft <= 0) return undefined;

    const intervalId = setInterval(() => {
      setTimeLeft((value) => Math.max(value - 1, 0));
    }, 1000);

    return () => clearInterval(intervalId);
  }, [auctionState?.active, timeLeft]);

  function handleBid(increment) {
    const amount = Number((highestBid + increment).toFixed(2));
    if (amount <= highestBid) {
      setError(`Bid must be more than ${formatMoney(highestBid)}`);
      return;
    }
    setError('');

    const myPlayer = players.find(p => p.id === myPlayerId);
    if (myPlayer && amount > parseFloat(myPlayer.balance)) {
      setError('Insufficient funds.');
      return;
    }

    const socket = getSocket();
    if (socket) {
      socket.emit('auction_bid', {
        match_id: matchId,
        property_id: property?.id,
        amount,
      });
    }
  }

  if (!auctionState?.active || !property) return null;

  const timerPct = (timeLeft / AUCTION_COUNTDOWN_SECONDS) * 100;
  const timerColor =
    timeLeft <= 2 ? '#ef4444' : timeLeft <= 3 ? '#f59e0b' : '#3b82f6';

  return (
    <div className="modal-overlay">
      <div className="modal-panel max-w-md">
        <h2 className="text-xl font-bold text-white mb-1">Auction</h2>

        {/* Property info */}
        <div className="flex items-center gap-3 bg-gray-800 rounded-lg p-3 mb-4">
          {property.group_color && (
            <div
              className="w-3 h-10 rounded-sm flex-shrink-0"
              style={{ backgroundColor: property.group_color }}
            />
          )}
          <div>
            <p className="text-white font-semibold">{property.name}</p>
            <p className="text-gray-400 text-xs">
              {property.region} · Base price {formatMoney(property.base_price)}
            </p>
          </div>
        </div>

        {/* Timer bar */}
        <div className="w-full bg-gray-800 rounded-full h-1.5 mb-1">
          <div
            key={timerResetKey}
            className="h-1.5 rounded-full transition-all duration-1000"
            style={{ width: `${timerPct}%`, backgroundColor: timerColor }}
          />
        </div>
        <p className="text-xs text-gray-500 text-right mb-4">{timeLeft}s to counter</p>

        {/* Current bid */}
        <div className="flex items-center justify-between bg-gray-800 rounded-lg px-4 py-3 mb-4">
          <div>
            <p className="text-xs text-gray-500 mb-0.5">Current bid</p>
            <p className="text-2xl font-bold text-green-300">{formatMoney(highestBid || 1)}</p>
          </div>
          {highestBidder && (
            <div className="flex items-center gap-2">
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: highestBidder.color_hex }}
              />
              <span className="text-sm text-gray-300">{highestBidder.username}</span>
            </div>
          )}
        </div>

        {/* Bid history */}
        {bids.length > 0 && (
          <div className="bg-gray-800 rounded-lg p-3 mb-4 max-h-28 overflow-y-auto">
            <p className="text-xs text-gray-500 mb-2">Bid history</p>
            <div className="space-y-1">
              {[...bids].reverse().map((bid, i) => {
                const bidder = players.find(p => p.id === bid.player_id);
                return (
                  <div key={i} className="flex justify-between text-xs">
                    <div className="flex items-center gap-1.5">
                      {bidder && (
                        <div
                          className="w-2 h-2 rounded-full"
                          style={{ backgroundColor: bidder.color_hex }}
                        />
                      )}
                      <span className="text-gray-300">{bidder?.username || `Player ${bid.player_id}`}</span>
                    </div>
                    <span className="text-green-400 font-mono">{formatMoney(bid.amount)}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <div className="grid grid-cols-3 gap-2">
          {BID_INCREMENTS.map((increment) => (
            <button
              key={increment}
              onClick={() => handleBid(increment)}
              className="btn-success btn-sm"
            >
              +{increment}
            </button>
          ))}
        </div>
        {error && <p className="text-red-400 text-xs mt-1">{error}</p>}

        <p className="text-center text-gray-600 text-xs mt-4">
          Each bid adds to the current price and resets the auction timer to 5 seconds.
        </p>
      </div>
    </div>
  );
}
