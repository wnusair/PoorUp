import { useGameStore } from '../../hooks/useGameState';
import { formatInflation } from '../../utils/formatters';

export default function HyperInflationBanner() {
  const { hyperInflation, economy, settings } = useGameStore();

  const round = Number(hyperInflation?.round ?? economy?.round_number ?? economy?.current_round ?? 0) || 0;
  const triggerRound = Number(settings?.hyper_inflation_round ?? 50) || 50;
  const inflationRate = hyperInflation?.econ?.inflation_rate
    ?? hyperInflation?.inflation_rate
    ?? hyperInflation?.inflation
    ?? economy?.inflation_rate
    ?? 0;

  if (!hyperInflation && round < triggerRound) return null;

  const pieces = ['HYPER-INFLATION ACTIVE'];
  if (round > 0) {
    pieces.push(`Round ${round}`);
  }
  pieces.push(`Rate ${formatInflation(inflationRate)}`);

  return (
    <div className="flex-shrink-0 border-b border-red-300/30 bg-red-700 px-4 py-2 text-center text-sm font-black uppercase tracking-[0.18em] text-white">
      {pieces.join(' • ')}
    </div>
  );
}
