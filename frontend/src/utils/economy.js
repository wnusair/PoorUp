import { calculateNetWorth } from './formatters';
import { normalizeGovernmentType } from './gameState';

export const WELFARE_TARGET_BUFFER = 200;

export const TAX_CATEGORIES = [
  ['income_tax', 'Income Tax'],
  ['property_tax', 'Property Tax'],
  ['turn_tax', 'Turn Tax'],
  ['luxury_tax', 'Luxury Tax'],
  ['super_tax', 'Super Tax'],
];

export const TURN_TAX_RATE_SHARE = 0.05;
export const LUXURY_TAX_RATE_SHARE = 0.5;
export const SUPER_TAX_RATE_SHARE = 1;

export function numberValue(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function clampNumber(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function roundCurrency(value) {
  return Math.round(numberValue(value, 0) * 100) / 100;
}

export function getEffectiveTaxRate(economy) {
  const taxMultiplier = Math.max(0, numberValue(economy?.tax_multiplier, 0));
  if (taxMultiplier <= 0) {
    return 0;
  }
  return taxMultiplier / (1 + taxMultiplier);
}

export function formatTaxRate(rate) {
  const percent = clampNumber(numberValue(rate, 0), 0, 1) * 100;
  return `${percent >= 10 ? percent.toFixed(1) : percent.toFixed(2)}%`;
}

function calculateCashTaxAmount(balance, rate) {
  const taxableCash = Math.max(0, numberValue(balance, 0));
  const safeRate = clampNumber(numberValue(rate, 0), 0, 1);
  return roundCurrency(Math.min(taxableCash, taxableCash * safeRate));
}

export function calculateIncomeTaxEstimate(balance, economy) {
  return calculateCashTaxAmount(balance, getEffectiveTaxRate(economy));
}

export function calculateTurnTaxEstimate(balance, economy) {
  return calculateCashTaxAmount(balance, getEffectiveTaxRate(economy) * TURN_TAX_RATE_SHARE);
}

export function calculateLuxuryTaxEstimate(balance, economy) {
  return calculateCashTaxAmount(balance, getEffectiveTaxRate(economy) * LUXURY_TAX_RATE_SHARE);
}

export function calculateSuperTaxEstimate(balance, economy) {
  return calculateCashTaxAmount(balance, getEffectiveTaxRate(economy) * SUPER_TAX_RATE_SHARE);
}

export function calculatePropertyTaxEstimate(properties, economy) {
  const taxMultiplier = Math.max(0, numberValue(economy?.tax_multiplier, 0));
  return roundCurrency(
    (properties || []).reduce((runningTotal, property) => {
      if (!property || property.is_mortgaged) {
        return runningTotal;
      }
      return runningTotal + (numberValue(property.current_value ?? property.base_price, 0) * 0.01 * taxMultiplier);
    }, 0),
  );
}

export function getPropertyTaxTiming(currentRound, settings) {
  const roundNumber = Math.max(1, numberValue(currentRound, 1));
  const interval = Math.max(1, numberValue(settings?.property_tax_every_n_rounds, 5));
  const remainder = roundNumber % interval;
  const nextRound = remainder === 0 ? roundNumber : roundNumber + (interval - remainder);
  const roundsUntilDue = Math.max(0, nextRound - roundNumber);
  const dueThisRound = roundsUntilDue === 0;

  return {
    dueThisRound,
    nextRound,
    roundsUntilDue,
    when: dueThisRound
      ? `At the end of your turn this round (round ${roundNumber}).`
      : `At the end of your turn in round ${nextRound} (${roundsUntilDue} round${roundsUntilDue === 1 ? '' : 's'} away).`,
  };
}

export function buildPlayerTaxSchedule({ player, properties, economy, settings, currentRound }) {
  const balance = numberValue(player?.balance, 0);
  const effectiveRate = getEffectiveTaxRate(economy);
  const propertyTiming = getPropertyTaxTiming(currentRound, settings);
  const turnTaxEnabled = Boolean(settings?.tax_every_turn);

  return [
    {
      id: 'income_tax',
      label: 'Income Tax',
      enabled: true,
      amount: calculateIncomeTaxEstimate(balance, economy),
      when: settings?.income_tax_on_pass_go
        ? 'When you pass GO and when you land on Income Tax.'
        : 'When you land on Income Tax.',
      detail: `${formatTaxRate(effectiveRate)} of your current cash.`,
    },
    {
      id: 'property_tax',
      label: 'Property Tax',
      enabled: true,
      amount: calculatePropertyTaxEstimate(properties, economy),
      when: propertyTiming.when,
      detail: 'Based on unmortgaged property value. This is the only tax that can push you into debt.',
      dueThisRound: propertyTiming.dueThisRound,
      nextRound: propertyTiming.nextRound,
    },
    {
      id: 'turn_tax',
      label: 'Turn Tax',
      enabled: turnTaxEnabled,
      amount: turnTaxEnabled ? calculateTurnTaxEstimate(balance, economy) : 0,
      when: turnTaxEnabled ? 'At the end of every turn.' : 'Disabled in this lobby.',
      detail: turnTaxEnabled
        ? `${formatTaxRate(effectiveRate * TURN_TAX_RATE_SHARE)} of your current cash.`
        : 'No turn tax is configured for this match.',
    },
    {
      id: 'luxury_tax',
      label: 'Luxury Tax',
      enabled: true,
      amount: calculateLuxuryTaxEstimate(balance, economy),
      when: 'When you land on Luxury Tax.',
      detail: `${formatTaxRate(effectiveRate * LUXURY_TAX_RATE_SHARE)} of your current cash.`,
    },
    {
      id: 'super_tax',
      label: 'Super Tax',
      enabled: true,
      amount: calculateSuperTaxEstimate(balance, economy),
      when: 'When you land on Super Tax.',
      detail: `${formatTaxRate(effectiveRate * SUPER_TAX_RATE_SHARE)} of your current cash.`,
    },
  ];
}

export function buildTaxRuleRows(economy, settings) {
  const effectiveRate = getEffectiveTaxRate(economy);
  const taxMultiplier = Math.max(0, numberValue(economy?.tax_multiplier, 0));
  const propertyTaxInterval = Math.max(1, numberValue(settings?.property_tax_every_n_rounds, 5));

  return [
    {
      label: 'Income Tax',
      enabled: true,
      formula: `${formatTaxRate(effectiveRate)} of current cash on Income Tax${settings?.income_tax_on_pass_go ? ', and after passing GO' : ''}`,
    },
    {
      label: 'Property Tax',
      enabled: true,
      formula: `1% of unmortgaged property value × ${taxMultiplier.toFixed(2)} every ${propertyTaxInterval} rounds`,
    },
    {
      label: 'Turn Tax',
      enabled: Boolean(settings?.tax_every_turn),
      formula: `${formatTaxRate(effectiveRate * TURN_TAX_RATE_SHARE)} of current cash at the end of each turn`,
    },
    {
      label: 'Luxury Tax',
      enabled: true,
      formula: `${formatTaxRate(effectiveRate * LUXURY_TAX_RATE_SHARE)} of current cash on the Luxury Tax space`,
    },
    {
      label: 'Super Tax',
      enabled: true,
      formula: `${formatTaxRate(effectiveRate * SUPER_TAX_RATE_SHARE)} of current cash on the Super Tax space`,
    },
  ];
}

function roundDistribution(rawShares, totalAmount) {
  const entries = Object.entries(rawShares || {});
  if (!entries.length) {
    return {};
  }

  const rounded = {};
  let runningTotal = 0;
  entries.slice(0, -1).forEach(([key, value]) => {
    const amount = roundCurrency(value);
    rounded[key] = amount;
    runningTotal += amount;
  });

  const [lastKey] = entries[entries.length - 1];
  rounded[lastKey] = roundCurrency(numberValue(totalAmount, 0) - runningTotal);
  return rounded;
}

export function getWelfareTargetBalance(settings) {
  const balanceCap = Math.max(0, numberValue(settings?.welfare_balance_cap, 0));
  const goSalary = Math.max(200, numberValue(settings?.go_salary, 200));
  const effectiveCap = balanceCap > 0 ? balanceCap : goSalary;
  return roundCurrency(effectiveCap + WELFARE_TARGET_BUFFER);
}

export function calculateProjectedWelfareAmount(balance, welfareRate, targetBalance) {
  const shortfall = Math.max(0, numberValue(targetBalance, 0) - numberValue(balance, 0));
  if (shortfall <= 0 || numberValue(welfareRate, 0) <= 0) {
    return 0;
  }
  return roundCurrency(shortfall * (clampNumber(numberValue(welfareRate, 0), 0, 100) / 100));
}

export function buildProjectedWelfare(players, economy, settings) {
  const governmentType = normalizeGovernmentType(
    economy?.gov_type || settings?.government_type || 'liberal_democracy',
  );
  const welfareEnabled = settings?.welfare_system_enabled ?? true;
  const welfareBalanceCap = Math.max(0, numberValue(settings?.welfare_balance_cap, 0));
  const welfareRate = clampNumber(numberValue(economy?.welfare_payout, 0), 0, 100);
  const treasuryBefore = Math.max(0, numberValue(economy?.treasury_balance, 0));
  const targetBalance = getWelfareTargetBalance(settings);

  const consideredPlayers = (players || []).filter((player) => {
    if (player?.bankrupt || player?.is_bankrupt) {
      return false;
    }
    if (welfareBalanceCap > 0 && numberValue(player?.balance, 0) > welfareBalanceCap) {
      return false;
    }
    return true;
  });

  const eligiblePlayers = consideredPlayers
    .map((player) => {
      const currentBalance = numberValue(player?.balance, 0);
      const projectedAmount = calculateProjectedWelfareAmount(currentBalance, welfareRate, targetBalance);
      const gapToTarget = Math.max(0, targetBalance - currentBalance);
      return {
        ...player,
        gapToTarget,
        projectedAmount,
      };
    })
    .filter((player) => player.projectedAmount > 0.009);

  const totalCost = roundCurrency(
    eligiblePlayers.reduce((sum, player) => sum + numberValue(player.projectedAmount, 0), 0),
  );

  const projection = {
    governmentType,
    welfareEnabled,
    welfareBalanceCap,
    welfareRate,
    targetBalance,
    targetBuffer: WELFARE_TARGET_BUFFER,
    consideredCount: consideredPlayers.length,
    eligiblePlayers,
    eligibleCount: eligiblePlayers.length,
    totalCost,
    averageAmount: eligiblePlayers.length ? roundCurrency(totalCost / eligiblePlayers.length) : 0,
    treasuryBefore,
    treasuryAfter: treasuryBefore,
    successful: false,
    reason: '',
  };

  if (!welfareEnabled) {
    projection.reason = 'Welfare is disabled in the current lobby settings.';
    return projection;
  }

  if (governmentType === 'minarchism') {
    projection.reason = 'Minarchism does not pay welfare.';
    return projection;
  }

  if (welfareRate <= 0) {
    projection.reason = 'Current welfare rate is 0.0%.';
    return projection;
  }

  if (!consideredPlayers.length) {
    projection.reason = 'No current players qualify for welfare.';
    return projection;
  }

  if (!eligiblePlayers.length) {
    projection.reason = 'Eligible players are already at or above the welfare target.';
    return projection;
  }

  if (treasuryBefore < projection.totalCost) {
    projection.reason = 'The treasury cannot cover the next welfare payment.';
    return projection;
  }

  projection.successful = true;
  projection.treasuryAfter = roundCurrency(treasuryBefore - projection.totalCost);
  return projection;
}

export function buildProjectedWelfareFunding(players, taxStats, totalCost) {
  const roundedTotal = roundCurrency(totalCost);
  const activePlayers = (players || []).filter((player) => !(player?.bankrupt || player?.is_bankrupt));
  if (!activePlayers.length || roundedTotal <= 0) {
    return { allocations: {}, basis: 'tax_paid_share' };
  }

  const playerTotals = taxStats?.player_totals || {};
  const taxWeights = activePlayers.reduce((accumulator, player) => {
    const totalTaxPaid = numberValue(playerTotals[String(player.id)]?.total_tax_paid, 0);
    if (totalTaxPaid > 0) {
      accumulator[String(player.id)] = totalTaxPaid;
    }
    return accumulator;
  }, {});

  const weightEntries = Object.entries(taxWeights);
  if (weightEntries.length) {
    const totalWeight = weightEntries.reduce((sum, [, amount]) => sum + amount, 0);
    const rawAllocations = Object.fromEntries(
      weightEntries.map(([playerId, amount]) => [playerId, roundedTotal * (amount / totalWeight)]),
    );
    return {
      allocations: roundDistribution(rawAllocations, roundedTotal),
      basis: 'tax_paid_share',
    };
  }

  const evenShare = roundedTotal / activePlayers.length;
  const rawAllocations = Object.fromEntries(
    activePlayers.map((player) => [String(player.id), evenShare]),
  );
  return {
    allocations: roundDistribution(rawAllocations, roundedTotal),
    basis: 'equal_split',
  };
}

export function buildPlayerFinanceSeries(playerFinanceHistory, playerId) {
  const historyEntries = playerFinanceHistory?.players?.[String(playerId)] || [];
  return historyEntries.map((entry, index) => ({
    ...entry,
    pointIndex: index,
    round: numberValue(entry.round, 0),
    turn_index: numberValue(entry.turn_index, 0),
    balance: numberValue(entry.balance, 0),
    net_worth: numberValue(entry.net_worth, 0),
    treasury_balance: numberValue(entry.treasury_balance, 0),
  }));
}

export function buildBudgetHistorySeries(taxStats, economy) {
  const rawHistory = Array.isArray(taxStats?.budget_history) ? taxStats.budget_history : [];
  const history = rawHistory
    .map((entry, index) => ({
      pointIndex: index,
      timestamp: entry?.timestamp || null,
      round: Math.max(0, numberValue(entry?.round, index + 1)),
      treasury_balance: numberValue(entry?.treasury_balance, 0),
      free_parking_claim: numberValue(entry?.free_parking_claim ?? entry?.free_parking_pot, 0),
      tax_collected: numberValue(entry?.tax_collected, 0),
      welfare_spend: numberValue(entry?.welfare_spend, 0),
      tax_total_to_date: numberValue(entry?.tax_total_to_date, 0),
      welfare_total_to_date: numberValue(entry?.welfare_total_to_date, 0),
    }))
    .sort((left, right) => left.round - right.round);

  if (history.length) {
    return history;
  }

  return [{
    pointIndex: 0,
    timestamp: null,
    round: Math.max(1, numberValue(economy?.round_number, 1)),
    treasury_balance: numberValue(economy?.treasury_balance, 0),
    free_parking_claim: numberValue(economy?.free_parking_pot, 0),
    tax_collected: 0,
    welfare_spend: 0,
    tax_total_to_date: numberValue(taxStats?.totals?.total_tax_paid, 0),
    welfare_total_to_date: numberValue(taxStats?.totals?.welfare_paid, 0),
  }];
}

export function buildCurrentNetWorthRows(players, properties) {
  return (players || []).map((player) => ({
    ...player,
    netWorth: calculateNetWorth(player, properties),
  }));
}