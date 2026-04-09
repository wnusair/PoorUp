import { useGameStore } from '../../hooks/useGameState';

const DOT_POSITIONS = {
  1: [[50, 50]],
  2: [[25, 25], [75, 75]],
  3: [[25, 25], [50, 50], [75, 75]],
  4: [[25, 25], [75, 25], [25, 75], [75, 75]],
  5: [[25, 25], [75, 25], [50, 50], [25, 75], [75, 75]],
  6: [[25, 20], [75, 20], [25, 50], [75, 50], [25, 80], [75, 80]],
};

function Die({ value, rolling }) {
  const dots = DOT_POSITIONS[value] || [];
  return (
    <div
      className={[
        'w-14 h-14 bg-white rounded-xl shadow-xl border-2 border-gray-300 relative',
        rolling ? 'animate-dice-roll' : '',
      ].join(' ')}
    >
      {dots.map(([cx, cy], i) => (
        <div
          key={i}
          className="w-3 h-3 bg-gray-900 rounded-full absolute"
          style={{
            left: `${cx}%`,
            top: `${cy}%`,
            transform: 'translate(-50%, -50%)',
          }}
        />
      ))}
    </div>
  );
}

export default function DiceDisplay() {
  const { diceResult, isRolling } = useGameStore();

  if (!diceResult && !isRolling) {
    return (
      <div className="flex gap-3 items-center justify-center opacity-30">
        <Die value={1} rolling={false} />
        <Die value={1} rolling={false} />
      </div>
    );
  }

  if (isRolling) {
    return (
      <div className="flex gap-3 items-center justify-center">
        <Die value={Math.ceil(Math.random() * 6)} rolling={true} />
        <Die value={Math.ceil(Math.random() * 6)} rolling={true} />
      </div>
    );
  }

  const { die1, die2, total } = diceResult;
  const isDoubles = die1 === die2;

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="flex gap-3 items-center justify-center animate-slide-up">
        <Die value={die1} rolling={false} />
        <Die value={die2} rolling={false} />
      </div>
      <div className="text-center">
        <span className="text-white font-bold text-lg">Total: {total}</span>
        {isDoubles && (
          <span className="ml-2 text-yellow-400 text-sm font-semibold animate-pulse">
            DOUBLES!
          </span>
        )}
      </div>
    </div>
  );
}
