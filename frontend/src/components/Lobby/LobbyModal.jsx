import { useMemo, useState } from 'react';
import HelpTooltip from '../Common/HelpTooltip';
import { useGameStore } from '../../hooks/useGameState';
import { gameLobby } from '../../utils/api';
import { formatMoney, formatRelativeTime } from '../../utils/formatters';
import { numberValue } from '../../utils/economy';
import { normalizeGovernmentType } from '../../utils/gameState';

const LOBBYING_BASE_SUCCESS_CHANCE = 0.18;
const LOBBYING_MAX_SUCCESS_CHANCE = 0.97;

const AXIS_ORDER = [
  'tax_multiplier',
  'welfare_rate',
  'bailouts',
  'capital_markets',
  'cash_bonus',
  'investor_mood',
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
        policy_name: 'Decrease Tax Rate',
        description: 'Lower future tax hits for every player.',
        cost_hint: 200,
      },
      increase: {
        label: 'Increase',
        target: 'tax_multiplier_increase',
        policy_name: 'Increase Tax Rate',
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
        policy_name: 'Decrease Welfare Rate',
        description: 'Reduce welfare payouts and preserve the treasury.',
        cost_hint: 220,
      },
      increase: {
        label: 'Increase',
        target: 'welfare_increase',
        policy_name: 'Increase Welfare Rate',
        description: 'Raise welfare support so low-balance players recover faster.',
        cost_hint: 250,
      },
    },
  },
  bailouts: {
    axis: 'bailouts',
    label: 'Bailouts',
    description: 'Decide whether the treasury can rescue insolvent players.',
    governmentTypes: ['liberal_democracy', 'social_democracy'],
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
  capital_markets: {
    axis: 'capital_markets',
    label: 'Investor Rules',
    description: 'Broad market lever. Use this when you want all liberal-democracy investor play hotter or calmer, not just the cash payout number.',
    governmentTypes: ['liberal_democracy'],
    directions: {
      expand: {
        label: 'Expand',
        target: 'market_deregulation',
        policy_name: 'Loosen Investor Rules',
        description: 'Best when you are leaning on investor deals or want a hotter market. Raises investor mood, but stability falls.',
        cost_hint: 280,
      },
      tighten: {
        label: 'Tighten',
        target: 'capital_controls',
        policy_name: 'Tighten Investor Rules',
        description: 'Best when rivals are farming market perks or the board is overheating. Lowers investor mood and raises stability.',
        cost_hint: 260,
      },
    },
  },
  cash_bonus: {
    axis: 'cash_bonus',
    label: 'Cash Bonus',
    description: 'Pure spare-cash lever. Use this when you expect to end rounds with money above the reserve floor.',
    governmentTypes: ['liberal_democracy'],
    directions: {
      increase: {
        label: 'Increase',
        target: 'cash_bonus_increase',
        policy_name: 'Increase Cash Bonus',
        description: 'Directly pays you more at round end for cash kept above the reserve floor.',
        cost_hint: 250,
      },
      decrease: {
        label: 'Decrease',
        target: 'cash_bonus_decrease',
        policy_name: 'Decrease Cash Bonus',
        description: 'Cuts everyone\'s spare-cash payout and usually makes the board calmer.',
        cost_hint: 230,
      },
    },
  },
  investor_mood: {
    axis: 'investor_mood',
    label: 'Investor Mood',
    description: 'Confidence-only lever. Use this when you want market perks stronger or weaker without changing the cash-bonus number.',
    governmentTypes: ['liberal_democracy'],
    directions: {
      boost: {
        label: 'Boost',
        target: 'investor_mood_increase',
        policy_name: 'Boost Investor Mood',
        description: 'Raises investor mood directly and strengthens the market side of liberal democracy.',
        cost_hint: 240,
      },
      cool: {
        label: 'Cool',
        target: 'investor_mood_decrease',
        policy_name: 'Cool Investor Mood',
        description: 'Cools investor mood directly and steadies the board without touching the cash-bonus rate.',
        cost_hint: 220,
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
        policy_name: 'Tighten Housing Rules',
        description: 'Cap rent growth and calm the economy.',
        cost_hint: 300,
      },
      loosen: {
        label: 'Loosen',
        target: 'deregulate_housing',
        policy_name: 'Loosen Housing Rules',
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
        policy_name: 'Rebuild Treasury',
        description: 'Inject cash into the treasury and lift stability.',
        cost_hint: 250,
      },
      stimulate: {
        label: 'Stimulate',
        target: 'economic_stimulus',
        policy_name: 'Fund Economic Stimulus',
        description: 'Spend treasury money on direct player relief.',
        cost_hint: 450,
      },
    },
  },
};

const AXIS_TOOLTIPS = {
  capital_markets: 'This controls what outside capital is allowed to do. Use Investor Mood if you only want to nudge confidence, or Cash Bonus if you want to change the round-end payout directly.',
  cash_bonus: 'Cash Bonus is the round-end percentage paid on money you keep above the reserve floor.',
  investor_mood: 'Investor Mood is market confidence. Higher mood makes liberal-democracy cash systems stronger, but it can also add social pressure.',
};

const DIRECTION_TOOLTIPS = {
  market_deregulation: 'Broadest upside lever. Use this when you want stronger investor play overall and can tolerate a hotter board.',
  capital_controls: 'Broadest safety lever. Use this when you want to cool rival investor play and buy back stability.',
  cash_bonus_increase: 'Most direct personal payout lever. This is the one to back if you expect to hold spare cash through round end.',
  cash_bonus_decrease: 'Use this when rivals are farming passive cash and you want a calmer board instead.',
  investor_mood_increase: 'Use this when you want stronger market perks without changing the cash-bonus percentage directly.',
  investor_mood_decrease: 'Use this when confidence is too hot and you want to calm the board without changing the cash-bonus percentage directly.',
};

const LIBERAL_DEMOCRACY_GUIDE = [
  {
    title: 'Cash Bonus',
    headline: 'Direct payout button',
    body: 'Best when you expect to finish rounds with cash above the reserve floor. This is the clearest personal money-maker.',
  },
  {
    title: 'Investor Mood',
    headline: 'Confidence only',
    body: 'Use this when you want stronger or weaker market perks without changing the cash-bonus number itself.',
  },
  {
    title: 'Investor Rules',
    headline: 'Broad market heat',
    body: 'Looser rules heat the board and push investor play harder. Tighter rules cool the board and cut rivals\' market edge.',
  },
];


function describeProjectedEffect(direction, economy) {
  const marketConfidence = numberValue(economy?.market_confidence, 0);
  const cashBonusRate = numberValue(economy?.capital_yield_rate, 0) * 100;
  const reserveFloor = numberValue(economy?.capital_yield_reserve_floor, 0);

  switch (direction?.target) {
    case 'market_deregulation':
      return `If this passes, Investor Mood rises above ${marketConfidence.toFixed(1)} and the market side of liberal democracy gets stronger, but stability slips.`;
    case 'capital_controls':
      return `If this passes, Investor Mood falls below ${marketConfidence.toFixed(1)} and the board steadies. Use it to cool rival investor play.`;
    case 'cash_bonus_increase':
      return `If this passes, the spare-cash bonus climbs above the current ${cashBonusRate.toFixed(2)}% rate on money you keep above ${formatMoney(reserveFloor)}.`;
    case 'cash_bonus_decrease':
      return `If this passes, the spare-cash bonus drops below the current ${cashBonusRate.toFixed(2)}% rate and the board gets calmer.`;
    case 'investor_mood_increase':
      return `If this passes, Investor Mood rises above ${marketConfidence.toFixed(1)} without changing the cash-bonus rate directly.`;
    case 'investor_mood_decrease':
      return `If this passes, Investor Mood falls below ${marketConfidence.toFixed(1)} without changing the cash-bonus rate directly.`;
    case 'bailout_enable':
      return 'If this passes, the treasury can rescue insolvent players again whenever it has enough cash.';
    case 'bailout_disable':
      return 'If this passes, the treasury stops rescuing insolvent players.';
    case 'tax_multiplier_decrease':
      return 'If this passes, future taxes get lighter.';
    case 'tax_multiplier_increase':
      return 'If this passes, taxes rise and the treasury refills faster.';
    case 'welfare_increase':
      return 'If this passes, low-cash players recover faster through welfare support.';
    case 'welfare_decrease':
      return 'If this passes, welfare pressure on the treasury eases.';
    case 'rent_control':
      return 'If this passes, rent growth gets capped and the economy calms down.';
    case 'deregulate_housing':
      return 'If this passes, rent and development upside get looser, which is better for landlords and worse for stability.';
    case 'stabilization_fund':
      return 'If this passes, the treasury gets rebuilt and stability improves.';
    case 'economic_stimulus':
      return 'If this passes, the treasury spends on direct relief for players.';
    default:
      return direction?.description || 'Pick a direction and fund it to change the board next round.';
  }
}

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
    target_stat: direction.target,
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

function getFallbackDirection(axisKey, directionKey) {
  return AXIS_FALLBACKS[axisKey]?.directions?.[directionKey] || null;
}

function resolveVisibleAxes(policyPools, governmentType) {
  const poolsByTarget = Object.values(policyPools || {}).reduce((accumulator, pool) => {
    if (pool?.target) {
      accumulator[pool.target] = pool;
    }
    return accumulator;
  }, {});

  return AXIS_ORDER.map((axisKey) => {
    const axis = AXIS_FALLBACKS[axisKey];
    if (axis.governmentTypes && !axis.governmentTypes.includes(governmentType)) {
      return null;
    }
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
  }).filter(Boolean);
}

function AxisDirectionButton({ direction, selected, onClick }) {
  const actionLabel = direction.policy_name || `${direction.label} ${direction.axis_label || 'Policy'}`;
  const actionMeta = [direction.axis_label, direction.direction_label || direction.label].filter(Boolean).join(' · ');

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
          <p className="text-[11px] uppercase tracking-[0.24em] text-gray-500">Action</p>
          <p className="mt-1 inline-flex items-center gap-1 text-sm font-semibold">
            <span>{actionLabel}</span>
            {DIRECTION_TOOLTIPS[direction.target] ? <HelpTooltip content={DIRECTION_TOOLTIPS[direction.target]} label={`${actionLabel} help`} /> : null}
          </p>
          {actionMeta ? <p className="mt-1 text-[11px] text-gray-500">{actionMeta}</p> : null}
          <p className="mt-2 text-xs leading-5 text-gray-400">{direction.description}</p>
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

function AxisCard({ axis, selectedEntry, onSelectDirection, onAmountChange, economy }) {
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
          <h3 className="mt-1 inline-flex items-center gap-2 text-lg font-semibold text-white">
            <span>{axis.label}</span>
            {AXIS_TOOLTIPS[axis.axis] ? <HelpTooltip content={AXIS_TOOLTIPS[axis.axis]} label={`${axis.label} help`} /> : null}
          </h3>
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
                {selectedDirection.policy_name || `${axis.label} · ${selectedDirection.label}`}
              </p>
              <p className="mt-1 text-[11px] text-gray-500">{axis.label} · {selectedDirection.direction_label || selectedDirection.label}</p>
              <p className="mt-1 text-sm text-cyan-200">
                {selectedAmount > 0 ? `${projectedOdds.toFixed(1)}% estimated odds after ${formatMoney(selectedAmount)}` : 'Select a direction and add money to project the pool.'}
              </p>
              <p className="mt-2 text-xs leading-5 text-gray-300">{describeProjectedEffect(selectedDirection, economy)}</p>
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
  const govType = normalizeGovernmentType(
    economy.gov_type || economy.government_type || settings?.government_type || 'liberal_democracy'
  );

  const visibleAxes = useMemo(
    () => resolveVisibleAxes(lobbyingStats?.policy_pools || {}, govType),
    [govType, lobbyingStats],
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
      .map(([axis, entry]) => {
        const axisDefinition = visibleAxes.find((candidate) => candidate.axis === axis);
        const fallbackDirection = getFallbackDirection(axis, entry?.direction);
        const selectedDirection = axisDefinition?.directions?.find((candidate) => candidate.direction === entry?.direction)
          || (fallbackDirection
            ? {
              ...fallbackDirection,
              axis: axisDefinition?.axis || axis,
              axis_label: axisDefinition?.label || AXIS_FALLBACKS[axis]?.label,
              direction: entry?.direction,
              direction_label: fallbackDirection.label,
              target_stat: fallbackDirection.target,
            }
            : null);
        return {
          axis,
          axis_label: axisDefinition?.label || AXIS_FALLBACKS[axis]?.label || null,
          direction: entry?.direction,
          direction_label: selectedDirection?.direction_label || selectedDirection?.label || null,
          target: selectedDirection?.target || fallbackDirection?.target || null,
          target_stat: selectedDirection?.target_stat || selectedDirection?.target || fallbackDirection?.target || null,
          policy_name: selectedDirection?.policy_name || fallbackDirection?.policy_name || null,
          policy_id: selectedDirection?.id ?? selectedDirection?.policy_id ?? null,
          amount: Math.max(0, numberValue(entry?.amount, 0)),
        };
      })
      .filter((entry) => entry.direction && entry.amount > 0);

    if (!payload.length) {
      setError('Pick at least one axis direction and add money to it.');
      return;
    }

    if (payload.some((entry) => !entry.target && !entry.target_stat && !entry.policy_id)) {
      setError('That policy selection is stale. Pick the direction again and resubmit.');
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
            <h2 className="mt-2 text-2xl font-bold text-white">Policy Actions</h2>
            <p className="mt-1 text-sm text-gray-400">
              Pick the policy direction you want, fund it, and the pool resolves at the end of the round.
            </p>
          </div>
          <button onClick={onClose} className="rounded-xl border border-gray-700 bg-gray-900 px-4 py-2 text-sm font-semibold text-gray-200 transition hover:border-gray-600 hover:text-white">
            Close
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          <div className="grid gap-4 lg:grid-cols-[1.18fr_0.82fr]">
            <div className="rounded-2xl border border-gray-800 bg-gray-950/70 p-4 text-sm text-gray-300">
              {govType === 'liberal_democracy'
                ? 'Cash Bonus is the direct payout lever. Investor Mood changes confidence without changing the payout rate. Investor Rules is the broad market-heat lever that pushes the whole investor side of the regime hotter or colder.'
                : 'Axis pools keep the economy visually coherent: taxes, welfare, bailouts, housing, and treasury posture all read as reversible policy directions instead of disconnected cards.'}
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

          {govType === 'liberal_democracy' && (
            <div className="rounded-3xl border border-cyan-900/50 bg-cyan-950/10 p-5 space-y-4">
              <div>
                <p className="text-sm font-semibold text-white">What Actually Helps You</p>
                <p className="mt-1 text-xs leading-5 text-gray-400">
                  Liberal democracy has three market levers, but only one of them is the direct cash-payout button.
                </p>
              </div>
              <div className="grid gap-3 md:grid-cols-3">
                {LIBERAL_DEMOCRACY_GUIDE.map((entry) => (
                  <div key={entry.title} className="rounded-2xl border border-gray-800 bg-gray-950/70 p-4">
                    <p className="text-xs uppercase tracking-[0.24em] text-cyan-400">{entry.title}</p>
                    <p className="mt-2 text-sm font-semibold text-white">{entry.headline}</p>
                    <p className="mt-2 text-xs leading-5 text-gray-400">{entry.body}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="grid gap-5 lg:grid-cols-[1.28fr_0.72fr]">
            <div className="space-y-4">
              {visibleAxes.map((axis) => (
                <AxisCard
                  key={axis.axis}
                  axis={axis}
                  selectedEntry={contributions[axis.axis]}
                  onSelectDirection={handleSelectDirection}
                  onAmountChange={handleAmountChange}
                  economy={economy}
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
                          {entry.success ? 'Passed' : 'Failed'} · {entry.policy_name || entry.direction_label || entry.target}
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