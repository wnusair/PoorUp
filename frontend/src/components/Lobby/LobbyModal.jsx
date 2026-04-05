import { useMemo, useState } from 'react';
import { useGameStore } from '../../hooks/useGameState';
import { gameLobby } from '../../utils/api';
import { formatMoney, formatRelativeTime } from '../../utils/formatters';
import { numberValue } from '../../utils/economy';

const LOBBYING_BASE_SUCCESS_CHANCE = 0.18;
const LOBBYING_MAX_SUCCESS_CHANCE = 0.97;

const AXIS_ORDER = [
  'tax_multiplier',
  'welfare_rate',
  'bailouts',
  'housing_regulation',
  'treasury_posture',
];

const AXIS_FALLBACKS = {
  tax_multiplier: {
    axis: 'tax_multiplier',
    label: 'Tax Multiplier',
    description: 'Lower taxes for relief or raise them to rebuild the treasury.',
    directions: {
      decrease: {
        label: 'Decrease',
        target: 'tax_multiplier_decrease',
        policy_name: 'Tax Relief',
        description: 'Lower future tax hits for every player.',
        cost_hint: 200,
      },
      increase: {
        label: 'Increase',
        target: 'tax_multiplier_increase',
        policy_name: 'Tax Hike',
        description: 'Raise taxes and feed the treasury faster.',
        cost_hint: 240,
      },
    },
  },
  welfare_rate: {
    axis: 'welfare_rate',
    label: 'Welfare Rate',
    description: 'Trim welfare drag or increase recovery support for low-cash players.',
    directions: {
      decrease: {
        label: 'Decrease',
        target: 'welfare_decrease',
        policy_name: 'Welfare Cuts',
        description: 'Reduce welfare payouts and preserve the treasury.',
        cost_hint: 220,
      },
      increase: {
        label: 'Increase',
        target: 'welfare_increase',
        policy_name: 'Welfare Increase',
        description: 'Raise welfare support so low-balance players recover faster.',
        cost_hint: 250,
      },
    },
  },
  bailouts: {
    axis: 'bailouts',
    label: 'Bailouts',
    description: 'Decide whether the treasury can rescue insolvent players.',
    directions: {
      disable: {
        label: 'Disable',
        target: 'bailout_disable',
        policy_name: 'Disable Bailouts',
        description: 'Keep insolvency a private-player risk.',
        cost_hint: 260,
      },
      enable: {
        label: 'Enable',
        target: 'bailout_enable',
        policy_name: 'Enable Bailouts',
        description: 'Let the treasury absorb debt spirals when it can afford to.',
        cost_hint: 260,
      },
    },
  },
  housing_regulation: {
    axis: 'housing_regulation',
    label: 'Housing Regulation',
    description: 'Tighten rent controls or loosen the market for development upside.',
    directions: {
      tighten: {
        label: 'Tighten',
        target: 'rent_control',
        policy_name: 'Rent Control',
        description: 'Cap rent growth and calm the economy.',
        cost_hint: 300,
      },
      loosen: {
        label: 'Loosen',
        target: 'deregulate_housing',
        policy_name: 'Housing Deregulation',
        description: 'Lift rent constraints and boost development value.',
        cost_hint: 400,
      },
    },
  },
  treasury_posture: {
    axis: 'treasury_posture',
    label: 'Treasury Posture',
    description: 'Rebuild state capacity or spend directly on stimulus.',
    directions: {
      rebuild: {
        label: 'Rebuild',
        target: 'stabilization_fund',
        policy_name: 'Stabilization Fund',
        description: 'Inject cash into the treasury and lift stability.',
        cost_hint: 250,
      },
      stimulate: {
        label: 'Stimulate',
        target: 'economic_stimulus',
        policy_name: 'Economic Stimulus',
        description: 'Spend treasury money on direct player relief.',
        cost_hint: 450,
      },
    },
  },
};

function calculateLobbyingSuccessChance({ totalContribution, contributorCount, costHint }) {
  const effectiveCostHint = Math.max(1, numberValue(costHint, 250));
  const contributionRatio = Math.max(0, numberValue(totalContribution, 0) / effectiveCostHint);
  const moneyBonus = Math.min(0.62, contributionRatio * 0.47);
  const contributorBonus = Math.min(0.15, Math.max(0, numberValue(contributorCount, 0) - 1) * 0.05);
  return (LOBBYING_BASE_SUCCESS_CHANCE + moneyBonus + contributorBonus) * 100;
}

function fallbackPool(axisKey, directionKey) {
  const axis = AXIS_FALLBACKS[axisKey];
  const direction = axis.directions[directionKey];
  return {
    axis: axisKey,
    axis_label: axis.label,
    direction: directionKey,
    direction_label: direction.label,
    target: direction.target,
    policy_name: direction.policy_name,
    description: direction.description,
    cost_hint: direction.cost_hint,
    estimated_success_chance: 18,
    progress_percent: 0,
    pool_total: 0,
    contributor_count: 0,
    contributors: [],
  };
}

function resolveVisibleAxes(policyPools) {
  const poolsByTarget = Object.values(policyPools || {}).reduce((accumulator, pool) => {
    if (pool?.target) {
      accumulator[pool.target] = pool;
    }
    return accumulator;
  }, {});

  return AXIS_ORDER.map((axisKey) => {
    const axis = AXIS_FALLBACKS[axisKey];
    return {
      ...axis,
      directions: Object.entries(axis.directions).map(([directionKey, directionDefinition]) => {
        const livePool = poolsByTarget[directionDefinition.target] || {};
        const fallback = fallbackPool(axisKey, directionKey);
        return {
          ...fallback,
          ...livePool,
          axis: livePool.axis || fallback.axis,
          axis_label: livePool.axis_label || fallback.axis_label,
          direction: livePool.direction || fallback.direction,
          direction_label: livePool.direction_label || fallback.direction_label,
          target: directionDefinition.target,
          policy_name: livePool.policy_name || fallback.policy_name,
          description: livePool.description || fallback.description,
          cost_hint: numberValue(livePool.cost_hint, fallback.cost_hint),
          estimated_success_chance: numberValue(livePool.estimated_success_chance, fallback.estimated_success_chance),
          progress_percent: numberValue(livePool.progress_percent, fallback.progress_percent),
          pool_total: numberValue(livePool.pool_total, fallback.pool_total),
          contributor_count: numberValue(livePool.contributor_count, (livePool.contributors || []).length),
          contributors: Array.isArray(livePool.contributors) ? livePool.contributors : fallback.contributors,
        };
      }),
    };
  });
}

function AxisDirectionButton({ direction, selected, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        'rounded-2xl border p-4 text-left transition',
        selected
          ? 'border-cyan-700/80 bg-cyan-950/30 text-cyan-100'
          : 'border-gray-800 bg-gray-950/70 text-gray-200 hover:border-gray-700',
      ].join(' ')}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">{direction.label}</p>
          <p className="mt-1 text-xs leading-5 text-gray-400">{direction.description}</p>
        </div>
        <span className="rounded-full border border-gray-700 bg-gray-900 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-gray-300">
          {Math.round(direction.progress_percent)}%
        </span>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-gray-900">
        <div
          className="h-full rounded-full bg-gradient-to-r from-cyan-500 via-sky-400 to-emerald-400 transition-all"
          style={{ width: `${Math.min(100, direction.progress_percent)}%` }}
        />
      </div>
      <div className="mt-3 flex items-center justify-between gap-3 text-[11px] text-gray-400">
        <span>{formatMoney(direction.pool_total)} in pool</span>
        <span>{direction.estimated_success_chance.toFixed(1)}% odds</span>
      </div>
      <div className="mt-1 flex items-center justify-between gap-3 text-[11px] text-gray-500">
        <span>{direction.contributor_count || 0} contributors</span>
        <span>Suggested {formatMoney(direction.cost_hint)}</span>
      </div>
    </button>
  );
}

function AxisCard({ axis, selectedEntry, onSelectDirection, onAmountChange }) {
  const selectedDirection = axis.directions.find((entry) => entry.direction === selectedEntry?.direction) || null;
  const selectedAmount = Math.max(0, numberValue(selectedEntry?.amount, 0));
  const projectedPoolTotal = selectedDirection
    ? numberValue(selectedDirection.pool_total, 0) + selectedAmount
    : 0;
  const projectedContributorCount = selectedDirection
    ? numberValue(selectedDirection.contributor_count, 0) + (selectedAmount > 0 ? 1 : 0)
    : 0;
  const projectedOdds = selectedDirection
    ? Math.min(
      LOBBYING_MAX_SUCCESS_CHANCE * 100,
      calculateLobbyingSuccessChance({
        totalContribution: projectedPoolTotal,
        contributorCount: projectedContributorCount,
        costHint: selectedDirection.cost_hint,
      }),
    )
    : 0;

  return (
    <div className="rounded-3xl border border-gray-800 bg-gray-950/80 p-5 space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.28em] text-gray-500">Policy Axis</p>
          <h3 className="mt-1 text-lg font-semibold text-white">{axis.label}</h3>
          <p className="mt-1 text-sm text-gray-400">{axis.description}</p>
        </div>
        <button
          type="button"
          onClick={() => onSelectDirection(axis.axis, null)}
          className="rounded-xl border border-gray-700 bg-gray-900 px-3 py-2 text-xs font-semibold text-gray-300 transition hover:border-gray-600 hover:text-white"
        >
          Clear
        </button>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        {axis.directions.map((direction) => (
          <AxisDirectionButton
            key={`${axis.axis}-${direction.direction}`}
            direction={direction}
            selected={selectedDirection?.direction === direction.direction}
            onClick={() => onSelectDirection(axis.axis, direction.direction)}
          />
        ))}
      </div>

      <div className="grid gap-3 md:grid-cols-[0.5fr_0.5fr] items-end">
        <label className="block text-xs font-medium uppercase tracking-wide text-gray-500">
          Contribution Amount
          <input
            type="number"
            min={0}
            step={10}
            value={selectedAmount}
            onChange={(event) => onAmountChange(axis.axis, Math.max(0, Number(event.target.value) || 0))}
            className="mt-2 w-full rounded-2xl border border-gray-700 bg-gray-900 px-4 py-3 text-sm text-white focus:border-cyan-500 focus:outline-none"
          />
        </label>

        <div className="rounded-2xl border border-gray-800 bg-gray-900/70 p-4 min-h-[92px]">
          {selectedDirection ? (
            <>
              <p className="text-[11px] uppercase tracking-[0.24em] text-gray-500">Projected Result</p>
              <p className="mt-2 text-sm font-semibold text-white">
                {axis.label} · {selectedDirection.label}
              </p>
              <p className="mt-1 text-sm text-cyan-200">
                {selectedAmount > 0 ? `${projectedOdds.toFixed(1)}% estimated odds after ${formatMoney(selectedAmount)}` : 'Select a direction and add money to project the pool.'}
              </p>
              {selectedAmount > 0 && (
                <p className="mt-1 text-xs text-gray-400">Projected pool total: {formatMoney(projectedPoolTotal)}</p>
              )}
            </>
          ) : (
            <div className="flex h-full items-center text-sm text-gray-500">
              Choose a direction first, then set the amount.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function LobbyModal({ matchId, onClose }) {
  const { players, economy, settings, myPlayerId, lobbyingStats } = useGameStore();
  const [contributions, setContributions] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  const me = players.find((player) => player.id === myPlayerId);
  const govType = economy.gov_type || settings?.government_type || 'liberal_democracy';

  const visibleAxes = useMemo(
    () => resolveVisibleAxes(lobbyingStats?.policy_pools || {}),
    [lobbyingStats],
  );

  const recentResolutions = useMemo(
    () => [...(lobbyingStats?.resolved_history || [])].slice(-8).reverse(),
    [lobbyingStats],
  );

  const totalContribution = useMemo(
    () => Object.values(contributions).reduce((sum, entry) => sum + Math.max(0, numberValue(entry?.amount, 0)), 0),
    [contributions],
  );

  const remainingBalance = numberValue(me?.balance, 0) - totalContribution;

  const handleSelectDirection = (axis, direction) => {
    setContributions((current) => {
      if (!direction) {
        return {
          ...current,
          [axis]: { direction: null, amount: 0 },
        };
      }

      const existing = current[axis] || { amount: 0 };
      return {
        ...current,
        [axis]: {
          direction,
          amount: direction === existing.direction ? existing.amount : Math.max(50, numberValue(existing.amount, 0)),
        },
      };
    });
  };

  const handleAmountChange = (axis, amount) => {
    setContributions((current) => ({
      ...current,
      [axis]: {
        ...(current[axis] || { direction: visibleAxes.find((entry) => entry.axis === axis)?.directions[0]?.direction || null }),
        amount,
      },
    }));
  };

  const handleSubmit = async () => {
    const payload = Object.entries(contributions)
      .map(([axis, entry]) => ({
        axis,
        direction: entry?.direction,
        amount: Math.max(0, numberValue(entry?.amount, 0)),
      }))
      .filter((entry) => entry.direction && entry.amount > 0);

    if (!payload.length) {
      setError('Pick at least one axis direction and add money to it.');
      return;
    }

    if (remainingBalance < 0) {
      setError('Your total lobbying spend is higher than your balance.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await gameLobby(matchId, { contributions: payload });
      setResult({
        message: response.data?.message || 'Lobbying contribution submitted.',
        contributions: response.data?.contributions || [],
        totalContribution: response.data?.total_contribution || totalContribution,
      });
      setContributions({});
    } catch (requestError) {
      setError(
        requestError.response?.data?.error
        || requestError.response?.data?.message
        || 'Lobby request failed',
      );
    } finally {
      setLoading(false);
    }
  };

  if (govType === 'minarchism') {
    return (
      <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
        <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-md shadow-2xl p-6 text-center">
          <p className="text-white font-bold text-lg">Lobbying Unavailable</p>
          <p className="text-gray-400 text-sm mt-2">
            The current government does not allow lobbying.
          </p>
          <button
            onClick={onClose}
            className="mt-4 px-6 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition"
          >
            Close
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="w-full max-w-6xl max-h-[calc(100vh-2rem)] overflow-hidden rounded-3xl border border-cyan-900/70 bg-gray-950 shadow-2xl flex flex-col">
        <div className="flex items-start justify-between gap-4 border-b border-gray-800 px-6 py-5">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-cyan-400">Lobbying</p>
            <h2 className="mt-2 text-2xl font-bold text-white">Policy Axes</h2>
            <p className="mt-1 text-sm text-gray-400">
              Each issue is one reversible axis. Pick a direction, size the spend, and watch the projected odds before you commit.
            </p>
          </div>
          <button onClick={onClose} className="rounded-xl border border-gray-700 bg-gray-900 px-4 py-2 text-sm font-semibold text-gray-200 transition hover:border-gray-600 hover:text-white">
            Close
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          <div className="grid gap-4 lg:grid-cols-[1.18fr_0.82fr]">
            <div className="rounded-2xl border border-gray-800 bg-gray-950/70 p-4 text-sm text-gray-300">
              Axis pools keep the economy visually coherent: taxes, welfare, bailouts, housing, and treasury posture all read as reversible policy directions instead of disconnected cards.
            </div>
            <div className="rounded-2xl border border-gray-800 bg-gray-950/70 p-4 grid grid-cols-2 gap-3">
              <div className="econ-stat">
                <span className="econ-stat__label">Your Balance</span>
                <span className="econ-stat__value text-amber-300">{formatMoney(me?.balance || 0)}</span>
              </div>
              <div className="econ-stat">
                <span className="econ-stat__label">Selected Spend</span>
                <span className="econ-stat__value text-cyan-300">{formatMoney(totalContribution)}</span>
              </div>
              <div className="econ-stat">
                <span className="econ-stat__label">After Submit</span>
                <span className={`econ-stat__value ${remainingBalance >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>
                  {formatMoney(remainingBalance)}
                </span>
              </div>
              <div className="econ-stat">
                <span className="econ-stat__label">Bailout Policy</span>
                <span className={`econ-stat__value ${economy?.bailout_enabled ? 'text-emerald-300' : 'text-rose-300'}`}>
                  {economy?.bailout_enabled ? 'Enabled' : 'Disabled'}
                </span>
              </div>
            </div>
          </div>

          <div className="grid gap-5 lg:grid-cols-[1.28fr_0.72fr]">
            <div className="space-y-4">
              {visibleAxes.map((axis) => (
                <AxisCard
                  key={axis.axis}
                  axis={axis}
                  selectedEntry={contributions[axis.axis]}
                  onSelectDirection={handleSelectDirection}
                  onAmountChange={handleAmountChange}
                />
              ))}
            </div>

            <div className="space-y-4">
              <div className="rounded-3xl border border-gray-800 bg-gray-950/80 p-5 space-y-3">
                <div>
                  <p className="text-sm font-semibold text-white">Submit Lobbying</p>
                  <p className="mt-1 text-xs leading-5 text-gray-400">
                    Contributions are spent immediately and resolve at the end of the round.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleSubmit}
                  disabled={loading}
                  className="w-full rounded-2xl bg-cyan-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:bg-gray-800 disabled:text-gray-500"
                >
                  {loading ? 'Submitting…' : 'Submit Contributions'}
                </button>
                {error && (
                  <div className="rounded-2xl border border-rose-900/70 bg-rose-950/30 px-4 py-3 text-sm text-rose-200">
                    {error}
                  </div>
                )}
                {result && (
                  <div className="rounded-2xl border border-emerald-900/70 bg-emerald-950/20 px-4 py-3 text-sm text-emerald-100 space-y-2">
                    <p className="font-semibold text-emerald-300">{result.message}</p>
                    <p>Total spend: {formatMoney(result.totalContribution)}</p>
                    {result.contributions.map((entry, index) => (
                      <p key={`${entry.axis || entry.policy?.axis || 'policy'}-${index}`} className="text-xs text-emerald-100/80">
                        {(entry.policy?.axis_label || entry.axis || 'Policy')} · {(entry.policy?.direction_label || entry.direction || 'Direction')} · {formatMoney(entry.contribution)}
                      </p>
                    ))}
                  </div>
                )}
              </div>

              <div className="rounded-3xl border border-gray-800 bg-gray-950/80 p-5 space-y-4">
                <div>
                  <p className="text-sm font-semibold text-white">Recent Results</p>
                  <p className="mt-1 text-xs leading-5 text-gray-400">Latest passed and failed lobbying resolutions.</p>
                </div>
                {recentResolutions.length === 0 ? (
                  <p className="text-sm text-gray-500">No policy pools have resolved yet.</p>
                ) : (
                  <div className="space-y-3">
                    {recentResolutions.map((entry, index) => (
                      <div key={`${entry.timestamp || index}-${entry.target || 'axis'}`} className="rounded-2xl border border-gray-800 bg-gray-900/70 px-4 py-3 space-y-1.5">
                        <div className="flex items-center justify-between gap-3 text-xs text-gray-500">
                          <span>{entry.axis_label || entry.policy_name}</span>
                          <span>{formatRelativeTime(entry.timestamp)}</span>
                        </div>
                        <p className={`text-sm font-semibold ${entry.success ? 'text-emerald-200' : 'text-rose-200'}`}>
                          {entry.success ? 'Passed' : 'Failed'} · {entry.direction_label || entry.policy_name}
                        </p>
                        <p className="text-xs leading-5 text-gray-300">
                          {entry.success
                            ? (entry.effect_summary || 'A lobbying effort succeeded.')
                            : (entry.reason || 'A lobbying effort failed.')}
                        </p>
                        <p className="text-[11px] text-gray-500">
                          Pool {formatMoney(entry.total_contribution)} · {numberValue(entry.success_chance, 0).toFixed(1)}% estimated odds
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}