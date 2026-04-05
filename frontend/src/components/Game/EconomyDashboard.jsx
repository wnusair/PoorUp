import { useGameStore } from '../../hooks/useGameState';
import { formatMoney, formatInflation } from '../../utils/formatters';
import { GOVERNMENT_TYPES } from '../../utils/constants';
import { normalizeGovernmentType } from '../../utils/gameState';

export default function EconomyDashboard() {
  const { economy } = useGameStore();
  const {
    inflation_rate = 0,
    welfare_payout = 0,
    treasury_balance = 0,
    free_parking_pot = 0,
    bailout_enabled = false,
    gov_type,
    government_type,
    round_number = 1,
  } = economy;
  const governmentKey = normalizeGovernmentType(gov_type || government_type || 'liberal_democracy');
  const govLabel = GOVERNMENT_TYPES[governmentKey]?.label || governmentKey;

  return (
    <div className="bg-gray-800 rounded-xl p-3 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Economy</h3>
        <span className="text-xs text-blue-400 font-medium">Round {round_number}</span>
      </div>

      {/* Government type */}
      <div className="flex items-center justify-between text-xs">
        <span className="text-gray-500">Government</span>
        <span className="text-purple-400 font-semibold">{govLabel}</span>
      </div>

      {/* Inflation */}
      <div className="flex items-center justify-between text-xs">
        <span className="text-gray-500">Inflation</span>
        <span
          className={[
            'font-mono font-bold',
            inflation_rate > 0.5 ? 'text-red-400' : inflation_rate > 0.2 ? 'text-yellow-400' : 'text-green-400',
          ].join(' ')}
        >
          {formatInflation(inflation_rate)}
        </span>
      </div>

      {/* Treasury */}
      <div className="flex items-center justify-between text-xs">
        <span className="text-gray-500">Treasury</span>
        <span className="text-yellow-400 font-mono">{formatMoney(treasury_balance)}</span>
      </div>

      <div className="flex items-center justify-between text-xs">
        <span className="text-gray-500">Free Parking Claim</span>
        <span className="text-cyan-300 font-mono">{formatMoney(free_parking_pot)}</span>
      </div>

      {/* Welfare */}
      <div className="flex items-center justify-between text-xs">
        <span className="text-gray-500">Welfare Rate</span>
        <span className="text-green-400 font-mono">{(Number(welfare_payout) || 0).toFixed(1)}%</span>
      </div>

      <div className="flex items-center justify-between text-xs">
        <span className="text-gray-500">Bailouts</span>
        <span className={bailout_enabled ? 'text-emerald-300 font-semibold' : 'text-rose-300 font-semibold'}>
          {bailout_enabled ? 'Enabled' : 'Disabled'}
        </span>
      </div>
    </div>
  );
}
