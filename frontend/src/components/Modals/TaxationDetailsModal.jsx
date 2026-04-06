import { useMemo, useState } from 'react';
import { useGameStore } from '../../hooks/useGameState';
import { GOVERNMENT_TYPES } from '../../utils/constants';
import {
  TAX_CATEGORIES,
  buildTaxRuleRows,
  buildBudgetHistorySeries,
  buildCurrentNetWorthRows,
  buildPlayerFinanceSeries,
  buildProjectedWelfare,
  buildProjectedWelfareFunding,
  numberValue,
} from '../../utils/economy';
import { formatExactMoney, formatInflation } from '../../utils/formatters';
import { normalizeGovernmentType } from '../../utils/gameState';

const TAB_OPTIONS = [
  ['overview', 'Overview'],
  ['welfare', 'Welfare'],
  ['taxation', 'Taxation'],
  ['players', 'Player Breakdown'],
];

const DEFAULT_BUDGET_HISTORY_ROUNDS = 15;
const EXPANDED_BUDGET_HISTORY_ROUNDS = 100;

function emptyPlayerTotals(player) {
  return {
    player_id: player?.id ?? null,
    username: player?.username || 'Player',
    income_tax: 0,
    property_tax: 0,
    turn_tax: 0,
    luxury_tax: 0,
    super_tax: 0,
    total_tax_paid: 0,
    welfare_contributed: 0,
    welfare_received: 0,
  };
}

function MetricCard({ label, value, tone = 'text-white', helper = '' }) {
  return (
    <div className="rounded-2xl border border-gray-800 bg-gray-950/80 p-4">
      <p className="text-[10px] uppercase tracking-[0.24em] text-gray-500">{label}</p>
      <p className={`mt-2 text-xl font-semibold ${tone}`}>{value}</p>
      {helper && <p className="mt-1 text-xs text-gray-500">{helper}</p>}
    </div>
  );
}

function TabButton({ active, label, onClick }) {
  return (
    <button
      onClick={onClick}
      className={[
        'rounded-full px-3 py-2 text-xs font-semibold uppercase tracking-wide transition',
        active
          ? 'border border-cyan-700 bg-cyan-950/60 text-cyan-200'
          : 'border border-gray-800 bg-gray-950 text-gray-400 hover:border-gray-700 hover:text-gray-200',
      ].join(' ')}
    >
      {label}
    </button>
  );
}

function formatAxisCurrency(value) {
  const amount = numberValue(value, 0);
  if (amount >= 1000) {
    return `$${(amount / 1000).toFixed(1)}k`;
  }
  return `$${Math.round(amount)}`;
}

function BudgetTrendChart({ history, expanded = false }) {
  if (!history.length) {
    return (
      <div className="rounded-2xl border border-dashed border-gray-800 bg-gray-950/70 p-6 text-sm text-gray-500">
        Round history will appear once the game has recorded at least one economy snapshot.
      </div>
    );
  }

  const width = expanded ? Math.max(1180, 104 + (Math.max(0, history.length - 1) * 24)) : 920;
  const height = expanded ? 460 : 360;
  const paddingX = 52;
  const topPadding = 20;
  const bottomPadding = expanded ? 56 : 44;
  const lineAreaHeight = expanded ? 182 : 138;
  const gapHeight = expanded ? 56 : 42;
  const barAreaHeight = expanded ? 152 : 108;
  const usableWidth = width - (paddingX * 2);
  const usableHeight = height - topPadding - bottomPadding;
  const lineBottom = topPadding + lineAreaHeight;
  const barTop = topPadding + lineAreaHeight + gapHeight;
  const barBottom = Math.min(height - bottomPadding, barTop + barAreaHeight);
  const lineMax = Math.max(
    1,
    ...history.map((entry) => Math.max(numberValue(entry.treasury_balance, 0), numberValue(entry.free_parking_claim, 0))),
  );
  const flowMax = Math.max(
    1,
    ...history.map((entry) => Math.max(numberValue(entry.tax_collected, 0), numberValue(entry.welfare_spend, 0))),
  );

  const pointX = (index) => {
    if (history.length === 1) {
      return width / 2;
    }
    return paddingX + ((usableWidth * index) / (history.length - 1));
  };

  const lineY = (value) => lineBottom - ((numberValue(value, 0) / lineMax) * Math.max(1, lineAreaHeight - 16));
  const barHeight = (value) => (numberValue(value, 0) / flowMax) * Math.max(1, barAreaHeight - 18);

  const treasuryPoints = history.map((entry, index) => `${pointX(index)},${lineY(entry.treasury_balance)}`).join(' ');
  const freeParkingPoints = history.map((entry, index) => `${pointX(index)},${lineY(entry.free_parking_claim)}`).join(' ');
  const groupWidth = Math.max(
    expanded ? 16 : 28,
    Math.min(expanded ? 32 : 66, (usableWidth / Math.max(history.length, 1)) * (expanded ? 0.78 : 0.62)),
  );
  const barGap = expanded ? 4 : 8;
  const barWidth = Math.max(expanded ? 5 : 8, (groupWidth - barGap) / 2);
  const treasuryPointRadius = expanded ? 3.5 : 4.25;
  const freeParkingPointRadius = expanded ? 3.25 : 4;
  const lineGridValues = expanded ? [0.2, 0.4, 0.6, 0.8, 1] : [0.25, 0.5, 0.75, 1];
  const barGridValues = expanded ? [0.25, 0.5, 0.75, 1] : [0.33, 0.66, 1];
  const xLabelStep = expanded ? Math.max(1, Math.ceil(history.length / 12)) : 1;
  const guideStep = expanded ? Math.max(1, Math.ceil(history.length / 24)) : 1;
  const chartHeightClass = expanded ? 'h-[28rem]' : 'h-[22rem]';
  const shouldScroll = expanded && history.length > 24;

  return (
    <div className="rounded-2xl border border-gray-800 bg-gray-950/70 p-4">
      <div className={expanded ? 'overflow-x-auto pb-2' : ''}>
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className={expanded ? `block max-w-none ${chartHeightClass}` : `w-full ${chartHeightClass}`}
          style={expanded ? { width: `${width}px`, minWidth: `${width}px` } : undefined}
        >
          <defs>
            <linearGradient id="budget-treasury-gradient" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#f59e0b" />
              <stop offset="100%" stopColor="#fde047" />
            </linearGradient>
            <linearGradient id="budget-freeparking-gradient" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#d946ef" />
              <stop offset="100%" stopColor="#fb7185" />
            </linearGradient>
            <linearGradient id="budget-tax-gradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#67e8f9" />
              <stop offset="100%" stopColor="#0ea5e9" />
            </linearGradient>
            <linearGradient id="budget-welfare-gradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#bef264" />
              <stop offset="100%" stopColor="#10b981" />
            </linearGradient>
          </defs>

          <rect x="0" y="0" width={width} height={height} rx="18" fill="#020617" />

          {lineGridValues.map((ratio) => {
            const y = lineBottom - (ratio * Math.max(1, lineAreaHeight - 16));
            return (
              <g key={`line-grid-${ratio}`}>
                <line x1={paddingX} y1={y} x2={width - paddingX} y2={y} stroke="#1f2937" strokeWidth="1" strokeDasharray="4 6" />
                <text x={paddingX - 10} y={y + 4} fill="#475569" fontSize="11" textAnchor="end">
                  {formatAxisCurrency(lineMax * ratio)}
                </text>
              </g>
            );
          })}

          {barGridValues.map((ratio) => {
            const y = barBottom - (ratio * Math.max(1, barAreaHeight - 18));
            return (
              <g key={`bar-grid-${ratio}`}>
                <line x1={paddingX} y1={y} x2={width - paddingX} y2={y} stroke="#111827" strokeWidth="1" strokeDasharray="3 5" />
                <text x={paddingX - 10} y={y + 4} fill="#334155" fontSize="11" textAnchor="end">
                  {formatAxisCurrency(flowMax * ratio)}
                </text>
              </g>
            );
          })}

          <line x1={paddingX} y1={lineBottom} x2={width - paddingX} y2={lineBottom} stroke="#334155" strokeWidth="1.2" />
          <line x1={paddingX} y1={barBottom} x2={width - paddingX} y2={barBottom} stroke="#334155" strokeWidth="1.2" />

          <text x={paddingX} y={14} fill="#94a3b8" fontSize="12" fontWeight="600" letterSpacing="0.14em">CUMULATIVE BALANCES</text>
          <text x={paddingX} y={barTop - 12} fill="#94a3b8" fontSize="12" fontWeight="600" letterSpacing="0.14em">PER-ROUND FLOW</text>

          <polyline
            fill="none"
            stroke="url(#budget-treasury-gradient)"
            strokeWidth="3.5"
            strokeLinejoin="round"
            strokeLinecap="round"
            points={treasuryPoints}
          />
          <polyline
            fill="none"
            stroke="url(#budget-freeparking-gradient)"
            strokeWidth="3"
            strokeLinejoin="round"
            strokeLinecap="round"
            points={freeParkingPoints}
          />

          {history.map((entry, index) => {
            const x = pointX(index);
            const taxBarHeight = barHeight(entry.tax_collected);
            const welfareBarHeight = barHeight(entry.welfare_spend);
            const showGuide = !expanded || index % guideStep === 0 || index === history.length - 1;
            const showRoundLabel = !expanded || index % xLabelStep === 0 || index === history.length - 1;

            return (
              <g key={`round-${entry.round}-${entry.pointIndex}`}>
                {showGuide && (
                  <line x1={x} y1={topPadding + 4} x2={x} y2={barBottom} stroke="#0f172a" strokeWidth="1" />
                )}
                <circle cx={x} cy={lineY(entry.treasury_balance)} r={treasuryPointRadius} fill="#fde047" stroke="#111827" strokeWidth="2" />
                <circle cx={x} cy={lineY(entry.free_parking_claim)} r={freeParkingPointRadius} fill="#fb7185" stroke="#111827" strokeWidth="2" />

                <rect
                  x={x - groupWidth / 2}
                  y={barBottom - taxBarHeight}
                  width={barWidth}
                  height={Math.max(3, taxBarHeight)}
                  rx="4"
                  fill="url(#budget-tax-gradient)"
                />
                <rect
                  x={x - groupWidth / 2 + barWidth + barGap}
                  y={barBottom - welfareBarHeight}
                  width={barWidth}
                  height={Math.max(3, welfareBarHeight)}
                  rx="4"
                  fill="url(#budget-welfare-gradient)"
                />

                {showRoundLabel && (
                  <text x={x} y={height - 18} fill="#94a3b8" fontSize="11" textAnchor="middle">
                    {`R${entry.round}`}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      {shouldScroll && (
        <p className="mt-2 text-xs text-gray-500">Scroll horizontally to inspect the full expanded range.</p>
      )}

      <div className="mt-4 grid gap-3 md:grid-cols-4">
        <div className="rounded-xl border border-amber-900/60 bg-amber-950/20 px-3 py-2 text-sm">
          <p className="text-[10px] uppercase tracking-[0.22em] text-amber-200/70">Treasury</p>
          <p className="mt-1 font-mono text-amber-300">Cumulative</p>
        </div>
        <div className="rounded-xl border border-fuchsia-900/60 bg-fuchsia-950/20 px-3 py-2 text-sm">
          <p className="text-[10px] uppercase tracking-[0.22em] text-fuchsia-200/70">Free Parking</p>
          <p className="mt-1 font-mono text-fuchsia-300">Cumulative</p>
        </div>
        <div className="rounded-xl border border-cyan-900/60 bg-cyan-950/20 px-3 py-2 text-sm">
          <p className="text-[10px] uppercase tracking-[0.22em] text-cyan-200/70">Tax Collected</p>
          <p className="mt-1 font-mono text-cyan-300">That round only</p>
        </div>
        <div className="rounded-xl border border-emerald-900/60 bg-emerald-950/20 px-3 py-2 text-sm">
          <p className="text-[10px] uppercase tracking-[0.22em] text-emerald-200/70">Welfare Paid</p>
          <p className="mt-1 font-mono text-emerald-300">That round only</p>
        </div>
      </div>
    </div>
  );
}

function PlayerNetWorthChart({ data }) {
  if (!data.length) {
    return (
      <div className="rounded-2xl border border-dashed border-gray-800 bg-gray-950/70 p-6 text-sm text-gray-500">
        No net-worth history has been recorded yet. New points are captured as the game state changes.
      </div>
    );
  }

  if (data.length === 1) {
    return (
      <div className="rounded-2xl border border-gray-800 bg-gray-950/70 p-6 text-sm text-gray-300">
        <p className="font-medium text-white">Opening snapshot</p>
        <p className="mt-2">Current net worth: <span className="font-mono text-cyan-300">{formatExactMoney(data[0].net_worth)}</span></p>
      </div>
    );
  }

  const width = 640;
  const height = 220;
  const padding = 24;
  const values = data.map((point) => numberValue(point.net_worth, 0));
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const range = Math.max(1, maxValue - minValue);

  const points = data.map((point, index) => {
    const x = padding + (index * (width - padding * 2)) / (data.length - 1);
    const y = height - padding - ((numberValue(point.net_worth, 0) - minValue) / range) * (height - padding * 2);
    return `${x},${y}`;
  }).join(' ');

  return (
    <div className="rounded-2xl border border-gray-800 bg-gray-950/70 p-4">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-56">
        <line x1={padding} y1={padding} x2={padding} y2={height - padding} stroke="#1f2937" strokeWidth="1" />
        <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="#1f2937" strokeWidth="1" />
        <polyline
          fill="none"
          stroke="#22d3ee"
          strokeWidth="3"
          strokeLinejoin="round"
          strokeLinecap="round"
          points={points}
        />
        {data.map((point, index) => {
          const x = padding + (index * (width - padding * 2)) / (data.length - 1);
          const y = height - padding - ((numberValue(point.net_worth, 0) - minValue) / range) * (height - padding * 2);
          return <circle key={`${point.timestamp}-${index}`} cx={x} cy={y} r="4" fill="#67e8f9" />;
        })}
      </svg>
      <div className="mt-3 flex items-center justify-between gap-3 text-xs text-gray-500">
        <span>Start: {formatExactMoney(values[0])}</span>
        <span>Low: {formatExactMoney(minValue)}</span>
        <span>High: {formatExactMoney(maxValue)}</span>
        <span>Now: {formatExactMoney(values[values.length - 1])}</span>
      </div>
    </div>
  );
}

function OverviewTab({ economy, settings, welfareProjection, taxStats, governmentLabel }) {
  const [isBudgetChartExpanded, setIsBudgetChartExpanded] = useState(false);
  const budgetHistory = useMemo(
    () => buildBudgetHistorySeries(taxStats, economy),
    [taxStats, economy],
  );
  const budgetHistoryLimit = isBudgetChartExpanded
    ? EXPANDED_BUDGET_HISTORY_ROUNDS
    : DEFAULT_BUDGET_HISTORY_ROUNDS;
  const visibleBudgetHistory = useMemo(
    () => budgetHistory.slice(-budgetHistoryLimit),
    [budgetHistory, budgetHistoryLimit],
  );
  const latestBudget = budgetHistory[budgetHistory.length - 1] || null;
  const previousBudget = budgetHistory.length > 1 ? budgetHistory[budgetHistory.length - 2] : null;
  const taxDeltaVsPrevious = latestBudget && previousBudget
    ? numberValue(latestBudget.tax_collected, 0) - numberValue(previousBudget.tax_collected, 0)
    : 0;
  const budgetHistoryMessage = budgetHistory.length > budgetHistoryLimit
    ? `Showing the most recent ${visibleBudgetHistory.length} of ${budgetHistory.length} recorded rounds.${isBudgetChartExpanded ? '' : ' Expand the graph to inspect up to 100 rounds.'}`
    : `Showing ${budgetHistory.length} recorded round${budgetHistory.length === 1 ? '' : 's'}.`;

  const ruleRows = [
    ['Government', governmentLabel],
    ['GO Salary', formatExactMoney(settings?.go_salary || 0)],
    ['Inflation', formatInflation(economy?.inflation_rate || 0)],
    ['Tax Multiplier', `${numberValue(economy?.tax_multiplier, 0).toFixed(2)}x`],
    ['Welfare Target', formatExactMoney(welfareProjection.targetBalance)],
    ['Welfare Cap', numberValue(settings?.welfare_balance_cap, 0) > 0 ? formatExactMoney(settings?.welfare_balance_cap) : 'No cap'],
    ['Bailouts', economy?.bailout_enabled ? 'Enabled' : 'Disabled'],
    ['Free Parking Jackpot', settings?.free_parking_pot_enabled ? 'Enabled' : 'Disabled'],
    ['Income Tax on Pass GO', settings?.income_tax_on_pass_go ? 'Enabled' : 'Disabled'],
    ['Turn Tax', settings?.tax_every_turn ? 'Enabled' : 'Disabled'],
  ];

  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-4">
        <MetricCard label="Government" value={governmentLabel} tone="text-cyan-300" />
        <MetricCard label="Treasury" value={formatExactMoney(economy?.treasury_balance || 0)} tone="text-amber-300" />
        <MetricCard label="Welfare Rate" value={`${numberValue(economy?.welfare_payout, 0).toFixed(1)}%`} tone="text-emerald-300" />
        <MetricCard label="Bailout Policy" value={economy?.bailout_enabled ? 'On' : 'Off'} tone={economy?.bailout_enabled ? 'text-emerald-300' : 'text-rose-300'} />
      </div>

      <div className={`grid gap-4 ${isBudgetChartExpanded ? 'xl:grid-cols-1' : 'xl:grid-cols-[1.15fr_0.85fr]'}`}>
        <div className="rounded-2xl border border-gray-800 bg-gray-950/70 p-5">
          <div className="flex items-center justify-between gap-3 mb-4">
            <div>
              <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-400">Budget History</h3>
              <p className="text-sm text-gray-500 mt-1">Treasury and Free Parking stay cumulative; tax intake and welfare spend reset each round so you can compare round-over-round movement.</p>
              <p className="text-sm text-gray-500 mt-1">{budgetHistoryMessage}</p>
            </div>
            <button
              type="button"
              onClick={() => setIsBudgetChartExpanded((current) => !current)}
              className="rounded-xl border border-gray-700 bg-gray-900 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-cyan-300 transition hover:border-cyan-600 hover:text-cyan-200"
            >
              {isBudgetChartExpanded ? 'Collapse Graph' : 'Expand Graph'}
            </button>
          </div>
          <BudgetTrendChart history={visibleBudgetHistory} expanded={isBudgetChartExpanded} />
          {latestBudget && (
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              <MetricCard
                label="Latest Round Tax"
                value={formatExactMoney(latestBudget.tax_collected)}
                tone="text-cyan-300"
                helper={previousBudget
                  ? `${taxDeltaVsPrevious >= 0 ? 'Up' : 'Down'} ${formatExactMoney(Math.abs(taxDeltaVsPrevious))} versus round ${previousBudget.round}.`
                  : 'Round 1 is the opening baseline.'}
              />
              <MetricCard
                label="Latest Welfare Spend"
                value={formatExactMoney(latestBudget.welfare_spend)}
                tone="text-emerald-300"
                helper="Shown per round, not cumulative."
              />
              <MetricCard
                label="Current Free Parking"
                value={formatExactMoney(latestBudget.free_parking_claim)}
                tone="text-fuchsia-300"
                helper="Claimed on Free Space and then removed from the treasury."
              />
            </div>
          )}
          <div className="mt-4 rounded-2xl border border-gray-800 bg-gray-900/70 px-4 py-3 text-sm text-gray-400">
            Every tax hit still lands in the treasury first. If the Free Parking jackpot is enabled, that tax value also becomes claimable on Free Space and is removed from the treasury when someone collects it.
          </div>
        </div>

        <div className="rounded-2xl border border-gray-800 bg-gray-950/70 p-5">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-400">Current Rules</h3>
          <div className="mt-4 space-y-2">
            {ruleRows.map(([label, value]) => (
              <div key={label} className="flex items-center justify-between gap-3 rounded-xl border border-gray-800 bg-gray-900/70 px-3 py-2 text-sm text-gray-300">
                <span className="text-gray-500">{label}</span>
                <span className="text-right text-white">{value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function WelfareTab({ players, taxStats, economy, welfareProjection }) {
  const funding = useMemo(
    () => buildProjectedWelfareFunding(players, taxStats, welfareProjection.totalCost),
    [players, taxStats, welfareProjection.totalCost],
  );

  const playerTotals = taxStats?.player_totals || {};
  const eligibleIds = new Set(welfareProjection.eligiblePlayers.map((player) => player.id));
  const projectedById = Object.fromEntries(
    welfareProjection.eligiblePlayers.map((player) => [String(player.id), player]),
  );

  const welfareRows = (players || []).map((player) => {
    const totals = {
      ...emptyPlayerTotals(player),
      ...(playerTotals[String(player.id)] || {}),
      username: player.username || playerTotals[String(player.id)]?.username || 'Player',
    };

    const projectedPlayer = projectedById[String(player.id)] || null;
    const projectedAmount = numberValue(projectedPlayer?.projectedAmount, 0);
    const budgetShare = welfareProjection.totalCost > 0
      ? (projectedAmount / welfareProjection.totalCost) * 100
      : 0;
    const projectedFunding = numberValue(funding.allocations[String(player.id)], 0);

    return {
      player,
      totals,
      projectedAmount,
      budgetShare,
      projectedFunding,
      eligible: eligibleIds.has(player.id),
      gapToTarget: numberValue(projectedPlayer?.gapToTarget, 0),
      netWelfare: numberValue(totals.welfare_received, 0) - numberValue(totals.welfare_contributed, 0),
    };
  });

  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-4">
        <MetricCard label="Projected Cost" value={formatExactMoney(welfareProjection.totalCost)} tone="text-emerald-300" />
        <MetricCard label="Recipients" value={String(welfareProjection.eligibleCount)} tone="text-cyan-300" />
        <MetricCard label="Average Payout" value={formatExactMoney(welfareProjection.averageAmount)} tone="text-lime-300" />
        <MetricCard label="Funding Basis" value={funding.basis === 'tax_paid_share' ? 'Tax Share' : 'Equal Split'} tone="text-amber-300" helper="Projected burden uses each player's share of taxes paid so far, or an even split if nobody has paid tax yet." />
      </div>

      {welfareProjection.reason && (
        <div className={`rounded-2xl border px-4 py-3 text-sm ${welfareProjection.successful ? 'border-emerald-900 bg-emerald-950/30 text-emerald-200' : 'border-rose-900 bg-rose-950/30 text-rose-200'}`}>
          {welfareProjection.reason}
        </div>
      )}

      <div className="rounded-2xl border border-gray-800 bg-gray-950/70 px-4 py-3 text-sm text-gray-400">
        Welfare does not pay everyone the same amount. Each eligible player gets the configured welfare percentage of their own gap to the welfare target, so players farther below the target receive larger payouts.
      </div>

      <div className="rounded-2xl border border-gray-800 bg-gray-950/70 p-5 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800 text-left text-xs uppercase tracking-wide text-gray-500">
              <th className="px-3 py-2 font-semibold">Player</th>
              <th className="px-3 py-2 font-semibold">Eligible</th>
              <th className="px-3 py-2 font-semibold">Projected Payout</th>
              <th className="px-3 py-2 font-semibold">Share of Budget</th>
              <th className="px-3 py-2 font-semibold">Projected Funding Share</th>
              <th className="px-3 py-2 font-semibold">Paid for Welfare</th>
              <th className="px-3 py-2 font-semibold">Received</th>
              <th className="px-3 py-2 font-semibold">Net Welfare</th>
            </tr>
          </thead>
          <tbody>
            {welfareRows.map((row) => (
              <tr key={row.player.id} className="border-b border-gray-900 text-gray-200 align-top">
                <td className="px-3 py-3">
                  <p className="font-medium text-white">{row.totals.username}</p>
                  <p className="text-xs text-gray-500">Balance {formatExactMoney(row.player.balance || 0)}</p>
                  {row.gapToTarget > 0 && (
                    <p className="text-xs text-gray-600">Gap to target {formatExactMoney(row.gapToTarget)}</p>
                  )}
                </td>
                <td className="px-3 py-3">
                  <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${row.eligible ? 'bg-emerald-950/70 text-emerald-300 border border-emerald-900' : 'bg-gray-900 text-gray-500 border border-gray-800'}`}>
                    {row.eligible ? 'Yes' : 'No'}
                  </span>
                </td>
                <td className="px-3 py-3 font-mono text-emerald-300">{formatExactMoney(row.projectedAmount)}</td>
                <td className="px-3 py-3 font-mono text-cyan-300">{row.budgetShare.toFixed(1)}%</td>
                <td className="px-3 py-3 font-mono text-amber-300">{formatExactMoney(row.projectedFunding)}</td>
                <td className="px-3 py-3 font-mono text-orange-300">{formatExactMoney(row.totals.welfare_contributed || 0)}</td>
                <td className="px-3 py-3 font-mono text-emerald-300">{formatExactMoney(row.totals.welfare_received || 0)}</td>
                <td className={`px-3 py-3 font-mono ${row.netWelfare >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>
                  {formatExactMoney(row.netWelfare)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TaxationTab({ players, taxStats, economy, settings }) {
  const playerTotals = taxStats?.player_totals || {};
  const rows = (players || []).map((player) => ({
    player,
    totals: {
      ...emptyPlayerTotals(player),
      ...(playerTotals[String(player.id)] || {}),
      username: player.username || playerTotals[String(player.id)]?.username || 'Player',
    },
  }));

  const aggregateTotals = {
    income_tax: numberValue(taxStats?.totals?.income_tax),
    property_tax: numberValue(taxStats?.totals?.property_tax),
    turn_tax: numberValue(taxStats?.totals?.turn_tax),
    luxury_tax: numberValue(taxStats?.totals?.luxury_tax),
    super_tax: numberValue(taxStats?.totals?.super_tax),
    total_tax_paid: numberValue(taxStats?.totals?.total_tax_paid),
  };
  const taxRuleRows = buildTaxRuleRows(economy, settings);

  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-5">
        {TAX_CATEGORIES.map(([category, label]) => (
          <MetricCard
            key={category}
            label={label}
            value={formatExactMoney(aggregateTotals[category])}
            tone="text-orange-300"
          />
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <div className="rounded-2xl border border-gray-800 bg-gray-950/70 p-5">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-400">Tax Rules</h3>
          <div className="mt-4 space-y-3">
            {taxRuleRows.map((rule) => (
              <div key={rule.label} className="rounded-xl border border-gray-800 bg-gray-900/70 px-3 py-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-medium text-white">{rule.label}</p>
                  <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${rule.enabled ? 'border border-cyan-800 bg-cyan-950/50 text-cyan-300' : 'border border-gray-800 bg-gray-950 text-gray-500'}`}>
                    {rule.enabled ? 'Active' : 'Off'}
                  </span>
                </div>
                <p className="mt-2 text-sm text-gray-400">{rule.formula}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-gray-800 bg-gray-950/70 p-5 overflow-x-auto">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-400">Per-Player Tax Totals</h3>
          <table className="mt-4 min-w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-left text-xs uppercase tracking-wide text-gray-500">
                <th className="px-3 py-2 font-semibold">Player</th>
                {TAX_CATEGORIES.map(([, label]) => (
                  <th key={label} className="px-3 py-2 font-semibold">{label}</th>
                ))}
                <th className="px-3 py-2 font-semibold">Total</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ player, totals }) => (
                <tr key={player.id} className="border-b border-gray-900 text-gray-200">
                  <td className="px-3 py-3">
                    <p className="font-medium text-white">{totals.username}</p>
                    <p className="text-xs text-gray-500">Balance {formatExactMoney(player.balance || 0)}</p>
                  </td>
                  {TAX_CATEGORIES.map(([category]) => (
                    <td key={category} className="px-3 py-3 font-mono text-orange-200">
                      {formatExactMoney(totals[category] || 0)}
                    </td>
                  ))}
                  <td className="px-3 py-3 font-mono text-orange-300">{formatExactMoney(totals.total_tax_paid || 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function PlayerBreakdownTab({ players, properties, playerFinanceHistory, lobbyingStats, taxStats, selectedPlayerId, onSelectPlayer }) {
  const netWorthRows = useMemo(
    () => buildCurrentNetWorthRows(players, properties),
    [players, properties],
  );

  const activePlayerId = players.some((player) => player.id === selectedPlayerId)
    ? selectedPlayerId
    : players[0]?.id;
  const activePlayer = netWorthRows.find((player) => player.id === activePlayerId) || null;
  const playerHistory = buildPlayerFinanceSeries(playerFinanceHistory, activePlayerId);
  const lobbyingTotals = lobbyingStats?.player_totals?.[String(activePlayerId)] || { policy_totals: {}, total_spent: 0 };
  const taxTotals = taxStats?.player_totals?.[String(activePlayerId)] || emptyPlayerTotals(activePlayer);
  const lobbyingPolicies = Object.entries(lobbyingTotals.policy_totals || {})
    .map(([target, value]) => ({ target, ...value }))
    .sort((left, right) => numberValue(right.amount, 0) - numberValue(left.amount, 0));

  const openingNetWorth = playerHistory[0]?.net_worth ?? activePlayer?.netWorth ?? 0;
  const latestNetWorth = playerHistory[playerHistory.length - 1]?.net_worth ?? activePlayer?.netWorth ?? 0;
  const netChange = latestNetWorth - openingNetWorth;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-2">
        {players.map((player) => (
          <button
            key={player.id}
            onClick={() => onSelectPlayer(player.id)}
            className={[
              'rounded-full border px-3 py-2 text-sm font-medium transition',
              activePlayerId === player.id
                ? 'border-cyan-700 bg-cyan-950/60 text-cyan-200'
                : 'border-gray-800 bg-gray-950 text-gray-400 hover:border-gray-700 hover:text-gray-200',
            ].join(' ')}
          >
            {player.username}
          </button>
        ))}
      </div>

      {activePlayer && (
        <div className="grid gap-4 lg:grid-cols-4">
          <MetricCard label="Current Net Worth" value={formatExactMoney(activePlayer.netWorth)} tone="text-cyan-300" />
          <MetricCard label="Net Change" value={formatExactMoney(netChange)} tone={netChange >= 0 ? 'text-emerald-300' : 'text-rose-300'} />
          <MetricCard label="Lobbying Spend" value={formatExactMoney(lobbyingTotals.total_spent || 0)} tone="text-fuchsia-300" />
          <MetricCard label="Welfare Net" value={formatExactMoney(numberValue(taxTotals.welfare_received, 0) - numberValue(taxTotals.welfare_contributed, 0))} tone="text-amber-300" />
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <div className="space-y-4">
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-400">Net Worth Over Time</h3>
            <p className="mt-1 text-sm text-gray-500">Net worth is current cash plus unmortgaged assets, minus mortgage debt.</p>
          </div>
          <PlayerNetWorthChart data={playerHistory} />
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl border border-gray-800 bg-gray-950/70 p-5">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-400">Lobbying Breakdown</h3>
            <div className="mt-4 space-y-2">
              {lobbyingPolicies.length ? lobbyingPolicies.map((policy) => (
                <div key={policy.target} className="flex items-center justify-between gap-3 rounded-xl border border-gray-800 bg-gray-900/70 px-3 py-3 text-sm">
                  <div>
                    <p className="font-medium text-white">{policy.policy_name || policy.target}</p>
                    <p className="text-xs text-gray-500">Spent on this target so far</p>
                  </div>
                  <span className="font-mono text-fuchsia-300">{formatExactMoney(policy.amount || 0)}</span>
                </div>
              )) : (
                <p className="text-sm text-gray-500">No lobbying spend recorded for this player yet.</p>
              )}
            </div>
          </div>

          <div className="rounded-2xl border border-gray-800 bg-gray-950/70 p-5">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-400">Current Snapshot</h3>
            <div className="mt-4 space-y-2 text-sm">
              <div className="flex items-center justify-between gap-3 rounded-xl border border-gray-800 bg-gray-900/70 px-3 py-2">
                <span className="text-gray-500">Balance</span>
                <span className="font-mono text-white">{formatExactMoney(activePlayer?.balance || 0)}</span>
              </div>
              <div className="flex items-center justify-between gap-3 rounded-xl border border-gray-800 bg-gray-900/70 px-3 py-2">
                <span className="text-gray-500">Total Tax Paid</span>
                <span className="font-mono text-orange-300">{formatExactMoney(taxTotals.total_tax_paid || 0)}</span>
              </div>
              <div className="flex items-center justify-between gap-3 rounded-xl border border-gray-800 bg-gray-900/70 px-3 py-2">
                <span className="text-gray-500">Paid for Welfare</span>
                <span className="font-mono text-amber-300">{formatExactMoney(taxTotals.welfare_contributed || 0)}</span>
              </div>
              <div className="flex items-center justify-between gap-3 rounded-xl border border-gray-800 bg-gray-900/70 px-3 py-2">
                <span className="text-gray-500">Received from Welfare</span>
                <span className="font-mono text-emerald-300">{formatExactMoney(taxTotals.welfare_received || 0)}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function TaxationDetailsModal({ onClose }) {
  const {
    players,
    properties,
    economy,
    settings,
    taxStats,
    lobbyingStats,
    playerFinanceHistory,
  } = useGameStore();
  const [activeTab, setActiveTab] = useState('overview');
  const [selectedPlayerId, setSelectedPlayerId] = useState(players[0]?.id ?? null);

  const governmentType = normalizeGovernmentType(
    economy?.gov_type || settings?.government_type || 'liberal_democracy',
  );
  const governmentLabel = GOVERNMENT_TYPES[governmentType]?.label || governmentType;

  const welfareProjection = useMemo(
    () => buildProjectedWelfare(players, economy, settings),
    [players, economy, settings],
  );

  const activeTabContent = (() => {
    if (activeTab === 'welfare') {
      return (
        <WelfareTab
          players={players}
          taxStats={taxStats}
          economy={economy}
          welfareProjection={welfareProjection}
        />
      );
    }

    if (activeTab === 'taxation') {
      return (
        <TaxationTab
          players={players}
          taxStats={taxStats}
          economy={economy}
          settings={settings}
        />
      );
    }

    if (activeTab === 'players') {
      return (
        <PlayerBreakdownTab
          players={players}
          properties={properties}
          playerFinanceHistory={playerFinanceHistory}
          lobbyingStats={lobbyingStats}
          taxStats={taxStats}
          selectedPlayerId={selectedPlayerId}
          onSelectPlayer={setSelectedPlayerId}
        />
      );
    }

    return (
      <OverviewTab
        economy={economy}
        settings={settings}
        welfareProjection={welfareProjection}
        taxStats={taxStats}
        governmentLabel={governmentLabel}
      />
    );
  })();

  return (
    <div className="modal-overlay">
      <div className="w-full max-w-7xl max-h-[calc(100vh-2rem)] overflow-hidden rounded-3xl border border-gray-800 bg-gray-950 shadow-2xl flex flex-col">
        <div className="border-b border-gray-800 bg-gray-950 px-6 py-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-cyan-400">Economy</p>
              <h2 className="mt-2 text-2xl font-bold text-white">Economy Panel</h2>
              <p className="mt-1 text-sm text-gray-400">
                Rules, welfare, taxes, treasury flow, and per-player financial history in one fixed workspace.
              </p>
            </div>
            <button onClick={onClose} className="btn-ghost btn-sm">
              Close
            </button>
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            {TAB_OPTIONS.map(([tabKey, label]) => (
              <TabButton
                key={tabKey}
                active={activeTab === tabKey}
                label={label}
                onClick={() => setActiveTab(tabKey)}
              />
            ))}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          {activeTabContent}
        </div>
      </div>
    </div>
  );
}