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