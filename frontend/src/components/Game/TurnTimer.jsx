import { useEffect, useState, useRef } from 'react';
import { useGameStore } from '../../hooks/useGameState';
import { formatCountdown } from '../../utils/formatters';

export default function TurnTimer({ onExpire }) {
  const { settings, currentPlayerId, myPlayerId } = useGameStore();
  const timerEnabled = settings?.turn_timer_enabled !== false;
  const limitSec = settings?.turn_time_limit_seconds || 60;
  const [remaining, setRemaining] = useState(limitSec);
  const intervalRef = useRef(null);
  const expiredRef = useRef(false);

  // Reset timer whenever the current player changes
  useEffect(() => {
    if (!timerEnabled || limitSec <= 0) {
      setRemaining(limitSec);
      clearInterval(intervalRef.current);
      return undefined;
    }

    setRemaining(limitSec);
    expiredRef.current = false;
    clearInterval(intervalRef.current);

    intervalRef.current = setInterval(() => {
      setRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(intervalRef.current);
          if (!expiredRef.current) {
            expiredRef.current = true;
            onExpire && onExpire();
          }
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(intervalRef.current);
  }, [currentPlayerId, limitSec, timerEnabled]);

  if (!timerEnabled || limitSec <= 0) {
    return null;
  }

  const pct = (remaining / limitSec) * 100;
  const isCritical = remaining <= 5;
  const isWarning = remaining <= 15;

  const barColor = isCritical
    ? 'bg-red-500'
    : isWarning
    ? 'bg-yellow-400'
    : 'bg-green-500';

  const textColor = isCritical
    ? 'text-red-400'
    : isWarning
    ? 'text-yellow-400'
    : 'text-gray-300';

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs text-gray-500">
        <span>Turn Timer</span>
        <span className={`font-mono font-bold text-sm ${textColor} ${isCritical ? 'animate-pulse' : ''}`}>
          {formatCountdown(remaining)}
        </span>
      </div>
      <div className="w-full h-2 bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${barColor} ${isCritical ? 'animate-pulse-fast' : ''}`}
          style={{ width: `${pct}%`, transition: 'width 1s linear' }}
        />
      </div>
    </div>
  );
}
