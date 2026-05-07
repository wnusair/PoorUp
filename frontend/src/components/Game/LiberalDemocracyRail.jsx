import { useEffect, useMemo, useState } from 'react';
import { useGameStore } from '../../hooks/useGameState';
import { formatMoney } from '../../utils/formatters';
import { buildPlayerFinanceSeries } from '../../utils/economy';

const PANEL_TABS = [
  { key: 'portfolio', label: 'Portfolio' },
  { key: 'market', label: 'Market' },
  { key: 'bank', label: 'Bank' },
  { key: 'work', label: 'Work' },
  { key: 'taxes', label: 'Taxes' },
  { key: 'politics', label: 'Politics' },
];

const RANGE_OPTIONS = [
  { key: '5', label: '5R', count: 5 },
  { key: '10', label: '10R', count: 10 },
  { key: 'all', label: 'All', count: Infinity },
];

function StatRow({ label, value, tone = 'text-white' }) {
  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <span className="text-slate-400">{label}</span>
      <span className={`font-medium text-right ${tone}`}>{value}</span>
    </div>
  );
}

function SmallField({ label, children }) {
  return (
    <label className="block space-y-1">
      <span className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{label}</span>
      {children}
    </label>
  );
}

function ActionNotice({ notice }) {
  if (!notice) {
    return null;
  }

  return (
    <div className={`rounded-lg border px-3 py-2 text-xs ${notice.tone === 'error' ? 'border-rose-900/70 bg-rose-950/30 text-rose-200' : 'border-emerald-900/70 bg-emerald-950/20 text-emerald-200'}`}>
      {notice.message}
    </div>
  );
}

function buildErrorMessage(error, fallback) {
  if (!error) {
    return fallback;
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

function normalizedHistory(asset) {
  const history = Array.isArray(asset?.history) ? asset.history : [];
  if (history.length >= 2) {
    return history
      .map((entry, index) => ({
        round: Number(entry.round ?? index + 1) || index + 1,
        price: Number(entry.price) || 0,
      }))
      .filter((entry) => entry.price > 0);
  }

  const price = Number(asset?.price || 0);
  if (price <= 0) {
    return [];
  }
  const change = Number(asset?.price_change_last_round || asset?.change || 0);
  const previousPrice = change === -1 ? price : price / Math.max(0.05, 1 + change);
  const currentRound = Number(asset?.round || 1);
  return [
    { round: Math.max(1, currentRound - 1), price: previousPrice },
    { round: currentRound, price },
  ];
}

function Sparkline({ asset, rangeKey }) {
  const points = useMemo(() => {
    const option = RANGE_OPTIONS.find((entry) => entry.key === rangeKey) || RANGE_OPTIONS[0];
    const history = normalizedHistory(asset);
    return option.count === Infinity ? history : history.slice(-option.count);
  }, [asset, rangeKey]);

  if (points.length < 2) {
    return (
      <div className="flex h-28 items-center justify-center rounded-xl border border-slate-800 bg-slate-950 text-xs text-slate-500">
        No price history yet
      </div>
    );
  }

  const width = 260;
  const height = 112;
  const prices = points.map((point) => point.price);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const span = Math.max(1, max - min);
  const coords = points.map((point, index) => {
    const x = (index / Math.max(1, points.length - 1)) * width;
    const y = height - ((point.price - min) / span) * (height - 18) - 9;
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  });
  const path = `M ${coords.join(' L ')}`;
  const positive = points[points.length - 1].price >= points[0].price;

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950 p-3">
      <svg viewBox={`0 0 ${width} ${height}`} className="h-28 w-full" role="img" aria-label={`${asset?.label || asset?.asset_key || 'Asset'} price chart`}>
        <defs>
          <linearGradient id="ld-market-fill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={positive ? '#34d399' : '#fb7185'} stopOpacity="0.32" />
            <stop offset="100%" stopColor={positive ? '#34d399' : '#fb7185'} stopOpacity="0" />
          </linearGradient>
        </defs>
        <polyline
          points={`0,${height} ${coords.join(' ')} ${width},${height}`}
          fill="url(#ld-market-fill)"
          stroke="none"
        />
        <path
          d={path}
          fill="none"
          stroke={positive ? '#34d399' : '#fb7185'}
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="3"
        />
      </svg>
      <div className="mt-1 flex items-center justify-between text-[11px] text-slate-500">
        <span>R{points[0].round}</span>
        <span>{formatMoney(points[0].price)} to {formatMoney(points[points.length - 1].price)}</span>
        <span>R{points[points.length - 1].round}</span>
      </div>
    </div>
  );
}

function NetWorthChart({ data, valueKey = 'net_worth', label = 'Total Net Worth', color = '#22d3ee' }) {
  if (data.length < 1) return null;

  const width = 520;
  const height = 160;
  const padding = 20;
  const values = data.map((p) => p[valueKey] || 0);

  if (data.length === 1) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-950 px-3 py-4 flex items-center justify-between">
        <span className="text-xs text-slate-400">{label}</span>
        <span className="text-sm font-bold text-white">{formatMoney(values[0])}</span>
      </div>
    );
  }

  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const span = Math.max(1, maxVal - minVal);
  const positive = values[values.length - 1] >= values[0];
  const strokeColor = positive ? color : '#fb7185';

  const coords = data.map((point, index) => {
    const x = padding + (index / Math.max(1, data.length - 1)) * (width - padding * 2);
    const y = height - padding - ((point[valueKey] - minVal) / span) * (height - padding * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const pathD = `M ${coords.join(' L ')}`;
  const fillPath = `M ${coords[0]} L ${coords.join(' L ')} L ${coords[coords.length - 1].split(',')[0]},${height - padding} L ${coords[0].split(',')[0]},${height - padding} Z`;

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950 p-3">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-32" role="img" aria-label={`${label} over time`}>
        <defs>
          <linearGradient id={`nw-fill-${valueKey}`} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={strokeColor} stopOpacity="0.28" />
            <stop offset="100%" stopColor={strokeColor} stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={fillPath} fill={`url(#nw-fill-${valueKey})`} stroke="none" />
        <path d={pathD} fill="none" stroke={strokeColor} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        {data.map((point, index) => {
          const x = padding + (index / Math.max(1, data.length - 1)) * (width - padding * 2);
          const y = height - padding - ((point[valueKey] - minVal) / span) * (height - padding * 2);
          return <circle key={`nw-${valueKey}-${index}`} cx={x} cy={y} r="3" fill={strokeColor} />;
        })}
      </svg>
      <div className="mt-1.5 flex items-center justify-between gap-3 text-[10px] text-slate-500">
        <span>R{data[0].round}: {formatMoney(values[0])}</span>
        <span className={positive ? 'text-cyan-400' : 'text-rose-400'}>{positive ? '+' : ''}{formatMoney(values[values.length - 1] - values[0])}</span>
        <span>Now: {formatMoney(values[values.length - 1])}</span>
      </div>
    </div>
  );
}

export default function LiberalDemocracyRail({ socketActions = {}, activePanel: activePanelProp, onPanelChange, embedded = false }) {
  const { myPlayerId, currentPlayerId, matchId, players, properties, economy, playerFinanceHistory } = useGameStore();
  const me = players.find((player) => player.id === myPlayerId) || null;
  const market = economy?.market || {};
  const assets = market?.assets || {};
  const bankAccounts = economy?.bank?.players || economy?.bank?.accounts || {};
  const jobs = economy?.jobs?.players || {};
  const taxBrackets = Array.isArray(economy?.tax_brackets)
    ? economy.tax_brackets
    : Array.isArray(economy?.tax_brackets?.brackets)
      ? economy.tax_brackets.brackets
      : [];
  const account = me ? (bankAccounts[String(me.id)] || {}) : {};
  const bankSavingsRate = Number(economy?.bank?.savings_interest_rate || 0);
  const job = me ? (jobs[String(me.id)] || {}) : {};
  const portfolio = me?.portfolio || {};
  const isMyTurn = myPlayerId != null && currentPlayerId === myPlayerId;

  const [activePanelLocal, setActivePanelLocal] = useState('portfolio');
  const activePanel = activePanelProp ?? activePanelLocal;
  const setActivePanel = onPanelChange ?? setActivePanelLocal;
  const [rangeKey, setRangeKey] = useState('5');
  const [portfolioChartAsset, setPortfolioChartAsset] = useState(null);
  const [marketForm, setMarketForm] = useState({ assetKey: '', side: 'buy', quantity: '1' });
  const [bankAmount, setBankAmount] = useState('100');
  const [marketBusy, setMarketBusy] = useState(false);
  const [bankBusy, setBankBusy] = useState(false);
  const [marketNotice, setMarketNotice] = useState(null);
  const [bankNotice, setBankNotice] = useState(null);

  const politics = economy?.politics || null;

  const ownedProperties = useMemo(
    () => Object.values(properties || {}).filter((property) => property.owner_id === myPlayerId),
    [myPlayerId, properties],
  );

  const portfolioValue = useMemo(() => {
    const stocks = Object.entries(portfolio?.stocks || {}).reduce((sum, [assetKey, quantity]) => (
      sum + ((Number(quantity) || 0) * (Number(assets?.[assetKey]?.price) || 0))
    ), 0);
    const crypto = Object.entries(portfolio?.crypto || {}).reduce((sum, [assetKey, quantity]) => (
      sum + ((Number(quantity) || 0) * (Number(assets?.[assetKey]?.price) || 0))
    ), 0);
    return stocks + crypto;
  }, [assets, portfolio?.crypto, portfolio?.stocks]);

  const propertyValue = useMemo(
    () => ownedProperties.reduce((sum, p) => sum + (Number(p.current_value || p.base_price) || 0), 0),
    [ownedProperties],
  );

  const myNetWorth = (Number(me?.balance) || 0) + portfolioValue + propertyValue + (Number(account?.savings_balance) || 0);

  const myBracket = useMemo(() => {
    if (!taxBrackets.length) return null;
    return taxBrackets.find((b) => {
      const min = Number(b.min_net_worth ?? 0);
      const max = b.max_net_worth == null ? Infinity : Number(b.max_net_worth);
      return myNetWorth >= min && myNetWorth <= max;
    }) || taxBrackets[taxBrackets.length - 1];
  }, [taxBrackets, myNetWorth]);

  const assetOptions = useMemo(
    () => Object.values(assets).sort((left, right) => String(left?.label || left?.asset_key || '').localeCompare(String(right?.label || right?.asset_key || ''))),
    [assets],
  );

  const selectedAsset = assets?.[marketForm.assetKey] || assetOptions[0] || null;
  const selectedDelta = Number(selectedAsset?.price_change_last_round || selectedAsset?.change || 0);
  const holdings = [
    ...Object.entries(portfolio?.stocks || {}).map(([assetKey, quantity]) => ({ assetKey, quantity, kind: 'stock' })),
    ...Object.entries(portfolio?.crypto || {}).map(([assetKey, quantity]) => ({ assetKey, quantity, kind: 'crypto' })),
  ];

  useEffect(() => {
    if (!marketForm.assetKey && assetOptions[0]?.asset_key) {
      setMarketForm((current) => ({ ...current, assetKey: assetOptions[0].asset_key }));
    }
  }, [assetOptions, marketForm.assetKey]);

  const submitMarketOrder = async () => {
    const quantity = Number(marketForm.quantity || 0);
    if (!marketForm.assetKey || quantity <= 0) {
      setMarketNotice({ tone: 'error', message: 'Pick an asset and enter a positive quantity.' });
      return;
    }
    if (!socketActions?.submitMarketOrder || !matchId) {
      setMarketNotice({ tone: 'error', message: 'Market trading is not available right now.' });
      return;
    }

    setMarketBusy(true);
    setMarketNotice(null);
    try {
      await socketActions.submitMarketOrder({
        match_id: matchId,
        asset_key: marketForm.assetKey,
        side: marketForm.side,
        quantity,
      });
      setMarketNotice({ tone: 'success', message: `${marketForm.side === 'buy' ? 'Bought' : 'Sold'} ${quantity} ${marketForm.assetKey}.` });
    } catch (error) {
      setMarketNotice({ tone: 'error', message: buildErrorMessage(error, 'Market order failed.') });
    } finally {
      setMarketBusy(false);
    }
  };

  const runBankAction = async (kind) => {
    const amount = Number(bankAmount || 0);
    if (amount <= 0) {
      setBankNotice({ tone: 'error', message: 'Enter a positive amount first.' });
      return;
    }

    const actionMap = {
      deposit: socketActions?.depositBankFunds,
      withdraw: socketActions?.withdrawBankFunds,
      loan: socketActions?.requestBankLoan,
      repay: socketActions?.repayBankLoan,
    };
    const action = actionMap[kind];
    if (!action || !matchId) {
      setBankNotice({ tone: 'error', message: 'Bank actions are not available right now.' });
      return;
    }

    setBankBusy(true);
    setBankNotice(null);
    try {
      await action({ match_id: matchId, amount });
      setBankNotice({ tone: 'success', message: `${kind === 'loan' ? 'Requested' : kind === 'repay' ? 'Repaid' : kind === 'deposit' ? 'Deposited' : 'Withdrew'} ${formatMoney(amount)}.` });
    } catch (error) {
      setBankNotice({ tone: 'error', message: buildErrorMessage(error, 'Bank action failed.') });
    } finally {
      setBankBusy(false);
    }
  };

  const portfolioHistory = useMemo(
    () => buildPlayerFinanceSeries(playerFinanceHistory, myPlayerId),
    [playerFinanceHistory, myPlayerId],
  );
  const portfolioChartPoints = portfolioHistory.filter((entry) => entry.portfolio_value > 0 || portfolioHistory.some((p) => p.portfolio_value > 0));

  const content = (
    <div className={embedded ? 'space-y-4' : ''}>
      {!embedded && (
        <>
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300">Liberal Democracy</h3>
              <p className="text-[11px] text-slate-500">Round market controls</p>
            </div>
            <span className={`rounded-full px-2 py-1 text-[11px] font-semibold ${market?.cycle?.phase === 'decay' ? 'bg-rose-950 text-rose-200' : 'bg-emerald-950 text-emerald-200'}`}>
              {market?.cycle?.phase === 'decay' ? 'Stocks Falling' : 'Stocks Rising'}
            </span>
          </div>
          <div className="mb-3 grid grid-cols-6 gap-1 rounded-xl border border-slate-800 bg-slate-900/80 p-1">
            {PANEL_TABS.map((tab) => (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActivePanel(tab.key)}
                className={`rounded-lg px-1.5 py-2 text-[11px] font-semibold transition ${activePanel === tab.key ? 'bg-cyan-400 text-slate-950' : 'text-slate-400 hover:bg-slate-800 hover:text-white'}`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </>
      )}

      {activePanel === 'portfolio' && (
        <div className="space-y-3">
          {/* My Portfolio Chart — always shown at top when history exists */}
          {portfolioChartPoints.length >= 1 && (
            <div className="space-y-1.5">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">My Portfolio Over Time</p>
              <NetWorthChart data={portfolioChartPoints} valueKey="net_worth" label="Total Net Worth" color="#22d3ee" />
              {portfolioChartPoints.some((p) => p.portfolio_value > 0) && (
                <NetWorthChart data={portfolioChartPoints} valueKey="portfolio_value" label="Stocks & Crypto Value" color="#a78bfa" />
              )}
            </div>
          )}

          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-lg border border-slate-800 bg-slate-900/60 px-2.5 py-2">
              <span className="text-[10px] text-slate-500">Cash</span>
              <p className="text-sm font-semibold text-emerald-300">{formatMoney(me?.balance || 0)}</p>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900/60 px-2.5 py-2">
              <span className="text-[10px] text-slate-500">Stocks & Crypto</span>
              <p className="text-sm font-semibold text-cyan-300">{formatMoney(portfolioValue)}</p>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900/60 px-2.5 py-2">
              <span className="text-[10px] text-slate-500">Properties ({ownedProperties.length})</span>
              <p className="text-sm font-semibold text-amber-300">{formatMoney(propertyValue)}</p>
            </div>
            <div className="rounded-lg border border-slate-700 bg-slate-900/80 px-2.5 py-2">
              <span className="text-[10px] text-slate-400">Total Wealth</span>
              <p className="text-sm font-bold text-white">{formatMoney(myNetWorth)}</p>
            </div>
          </div>

          {holdings.length > 0 && (
            <>
              <p className="text-[11px] text-slate-500">Tap a holding to see its price chart.</p>
              <div className="space-y-1.5">
                {holdings.map(({ assetKey, quantity, kind }) => {
                  const asset = assets?.[assetKey];
                  const delta = Number(asset?.price_change_last_round || asset?.change || 0);
                  const isSelected = portfolioChartAsset === assetKey;
                  return (
                    <button
                      key={`${kind}-${assetKey}`}
                      type="button"
                      onClick={() => setPortfolioChartAsset(isSelected ? null : assetKey)}
                      className={`w-full rounded-lg border px-2.5 py-2 text-left transition ${isSelected ? 'border-cyan-500 bg-cyan-950/30' : 'border-slate-700 bg-slate-900/60 hover:border-slate-600'}`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-semibold text-slate-200 truncate">{asset?.label || assetKey}</span>
                        <span className={`text-[11px] font-bold flex-shrink-0 ${delta >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>
                          {delta >= 0 ? '+' : ''}{(delta * 100).toFixed(1)}%
                        </span>
                      </div>
                      <div className="flex items-center justify-between mt-0.5">
                        <span className="text-[11px] text-slate-400">
                          {kind === 'stock' ? Number(quantity).toFixed(0) : Number(quantity).toFixed(4)} shares
                        </span>
                        <span className="text-[11px] text-slate-300">{formatMoney((Number(quantity) || 0) * (Number(asset?.price) || 0))}</span>
                      </div>
                    </button>
                  );
                })}
              </div>
              {portfolioChartAsset && assets?.[portfolioChartAsset] && (
                <div className="space-y-2">
                  <p className="text-[11px] text-slate-400 font-semibold">{assets[portfolioChartAsset]?.label || portfolioChartAsset} price history</p>
                  <Sparkline asset={assets[portfolioChartAsset]} rangeKey={rangeKey} />
                  <div className="flex gap-1">
                    {RANGE_OPTIONS.map((range) => (
                      <button
                        key={range.key}
                        type="button"
                        onClick={() => setRangeKey(range.key)}
                        className={`rounded-full px-3 py-1 text-[11px] font-semibold ${rangeKey === range.key ? 'bg-white text-slate-950' : 'bg-slate-900 text-slate-400 hover:text-white'}`}
                      >
                        {range.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
          {holdings.length === 0 && portfolioChartPoints.length === 0 && (
            <p className="rounded-xl border border-dashed border-slate-700 p-3 text-xs text-slate-500">
              No history yet. Your portfolio chart will appear after the first round.
            </p>
          )}
          {holdings.length === 0 && portfolioChartPoints.length > 0 && (
            <p className="rounded-xl border border-dashed border-slate-700 p-3 text-xs text-slate-500">
              You have no stocks or crypto yet. Buy some from the Market tab.
            </p>
          )}
        </div>
      )}

      {activePanel === 'market' && (
        <div className="space-y-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-white">{selectedAsset?.label || selectedAsset?.asset_key || 'Market'}</p>
              <p className="text-xs text-slate-500">{selectedAsset?.asset_key || 'Asset'} · Market mood: {Number(market?.sentiment || 0).toFixed(0)}/100</p>
            </div>
            <div className="text-right">
              <p className="text-lg font-bold text-white">{formatMoney(selectedAsset?.price || 0)}</p>
              <p className={selectedDelta >= 0 ? 'text-xs font-semibold text-emerald-300' : 'text-xs font-semibold text-rose-300'}>
                {selectedDelta >= 0 ? '+' : ''}{(selectedDelta * 100).toFixed(1)}%
              </p>
            </div>
          </div>

          <Sparkline asset={selectedAsset} rangeKey={rangeKey} />

          <div className="flex gap-1">
            {RANGE_OPTIONS.map((range) => (
              <button
                key={range.key}
                type="button"
                onClick={() => setRangeKey(range.key)}
                className={`rounded-full px-3 py-1 text-[11px] font-semibold ${rangeKey === range.key ? 'bg-white text-slate-950' : 'bg-slate-900 text-slate-400 hover:text-white'}`}
              >
                {range.label}
              </button>
            ))}
          </div>

          <ActionNotice notice={marketNotice} />
          <div className="grid grid-cols-2 gap-2">
            <SmallField label="Asset">
              <select
                value={marketForm.assetKey}
                onChange={(event) => setMarketForm((current) => ({ ...current, assetKey: event.target.value }))}
                className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-cyan-500 focus:outline-none"
              >
                {assetOptions.map((asset) => (
                  <option key={asset.asset_key} value={asset.asset_key}>
                    {asset.label || asset.asset_key}
                  </option>
                ))}
              </select>
            </SmallField>
            <SmallField label="Side">
              <select
                value={marketForm.side}
                onChange={(event) => setMarketForm((current) => ({ ...current, side: event.target.value }))}
                className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-cyan-500 focus:outline-none"
              >
                <option value="buy">Buy</option>
                <option value="sell">Sell</option>
              </select>
            </SmallField>
          </div>
          <div className="flex items-end gap-2">
            <SmallField label="Quantity">
              <input
                type="number"
                min="0.0001"
                step="0.0001"
                value={marketForm.quantity}
                onChange={(event) => setMarketForm((current) => ({ ...current, quantity: event.target.value }))}
                className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-cyan-500 focus:outline-none"
              />
            </SmallField>
            <button
              type="button"
              onClick={submitMarketOrder}
              disabled={marketBusy || !isMyTurn}
              className="rounded-lg bg-cyan-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:bg-slate-800 disabled:text-slate-500"
            >
              {marketBusy ? 'Sending...' : 'Place Order'}
            </button>
          </div>
          {!isMyTurn && <p className="text-[11px] text-slate-500">Market orders unlock on your turn.</p>}
        </div>
      )}

      {activePanel === 'bank' && (
        <div className="space-y-3">
          <StatRow label="Savings Balance" value={formatMoney(account?.savings_balance || 0)} tone="text-sky-300" />
          <StatRow label="Savings Rate (per round)" value={`${(bankSavingsRate * 100).toFixed(2)}%`} tone="text-emerald-300" />
          {account?.savings_balance > 0 && (
            <StatRow
              label="Est. interest this round"
              value={`+${formatMoney((Number(account.savings_balance) || 0) * bankSavingsRate)}`}
              tone="text-emerald-200"
            />
          )}
          <StatRow label="Loan Principal" value={formatMoney(account?.loan_principal || 0)} tone="text-rose-300" />
          <StatRow label="Loan Rate" value={`${(Number(account?.loan_interest_rate || 0) * 100).toFixed(2)}%`} tone="text-amber-300" />
          <ActionNotice notice={bankNotice} />
          <SmallField label="Amount">
            <input
              type="number"
              min="1"
              step="1"
              value={bankAmount}
              onChange={(event) => setBankAmount(event.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-cyan-500 focus:outline-none"
            />
          </SmallField>
          <div className="grid grid-cols-2 gap-2">
            {[
              ['deposit', 'Deposit'],
              ['withdraw', 'Withdraw'],
              ['loan', 'Request Loan'],
              ['repay', 'Repay Loan'],
            ].map(([kind, label]) => (
              <button
                key={kind}
                type="button"
                onClick={() => runBankAction(kind)}
                disabled={bankBusy || !isMyTurn}
                className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm font-semibold text-slate-200 transition hover:border-slate-600 disabled:cursor-not-allowed disabled:border-slate-800 disabled:text-slate-500"
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      )}

      {activePanel === 'work' && (
        <div className="space-y-3">
          <div className={`rounded-xl border px-3 py-2 text-sm font-semibold ${job?.employment_status === 'unemployed' ? 'border-rose-800/60 bg-rose-950/30 text-rose-200' : 'border-emerald-800/60 bg-emerald-950/20 text-emerald-200'}`}>
            {job?.employment_status === 'unemployed' ? 'You are unemployed' : 'You are employed'}
          </div>
          <StatRow label="Works at" value={job?.employer_name || 'No employer yet'} tone="text-cyan-200" />
          <StatRow label="Pay per round" value={formatMoney(job?.salary || 0)} tone="text-emerald-300" />
          {Number(job?.unemployment_rounds_remaining || 0) > 0 && (
            <StatRow label="Rounds until you can work again" value={String(job.unemployment_rounds_remaining)} tone="text-amber-300" />
          )}
          {(job?.event_history || []).slice(-3).map((entry, index) => (
            <p key={`${entry}-${index}`} className="rounded-lg border border-slate-800 bg-slate-900/70 px-3 py-2 text-xs text-slate-300">
              {entry}
            </p>
          ))}
        </div>
      )}

      {activePanel === 'politics' && (
        <div className="space-y-3">
          {!politics ? (
            <p className="text-xs text-slate-500">Political data will appear at the end of round 1.</p>
          ) : (
            <>
              <div className="rounded-xl border border-violet-900/60 bg-violet-950/20 px-3 py-2">
                <p className="text-[11px] uppercase tracking-[0.18em] text-violet-300">Political climate</p>
                <p className="mt-1 text-base font-bold text-white">{politics.label || 'Centre'}</p>
                <div className="mt-2">
                  <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-rose-500 via-violet-400 to-blue-500"
                      style={{ width: `${Math.round(((Number(politics.spectrum || 0) + 1) / 2) * 100)}%` }}
                    />
                  </div>
                  <div className="flex justify-between mt-0.5 text-[10px] text-slate-500">
                    <span>Far Left</span>
                    <span>Centre</span>
                    <span>Far Right</span>
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <div className="rounded-lg border border-emerald-900/50 bg-emerald-950/20 px-3 py-2">
                  <p className="text-[10px] uppercase tracking-[0.18em] text-emerald-400 mb-0.5">Governing party</p>
                  <p className="text-sm font-semibold text-white">{politics.governing_party || '—'}</p>
                </div>
                <div className="rounded-lg border border-slate-700 bg-slate-900/60 px-3 py-2">
                  <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500 mb-0.5">Main opposition</p>
                  <p className="text-sm font-semibold text-slate-200">{politics.opposition_party || '—'}</p>
                </div>
                {politics.fringe_party && (
                  <div className="rounded-lg border border-orange-900/50 bg-orange-950/20 px-3 py-2">
                    <p className="text-[10px] uppercase tracking-[0.18em] text-orange-400 mb-0.5">Fringe party (radicalized)</p>
                    <p className="text-sm font-semibold text-orange-200">{politics.fringe_party}</p>
                  </div>
                )}
              </div>

              <p className="text-[11px] text-slate-500 px-1">
                Political climate shifts left when there are protests and strikes. High stability pushes it right.
              </p>
            </>
          )}
        </div>
      )}

      {activePanel === 'taxes' && (
        <div className="space-y-3">
          <div className="rounded-xl border border-fuchsia-900/60 bg-fuchsia-950/20 px-3 py-2">
            <p className="text-[11px] uppercase tracking-[0.18em] text-fuchsia-300">Your wealth right now</p>
            <p className="mt-1 text-base font-bold text-white">{formatMoney(myNetWorth)}</p>
            {myBracket && (
              <p className="mt-1 text-xs text-fuchsia-200">
                You are in <span className="font-semibold">{myBracket.label}</span> — paying <span className="font-semibold">{(Number(myBracket.rate || 0) * 100).toFixed(1)}%</span> per round on net worth
              </p>
            )}
          </div>

          {/* Income vs Tax breakdown */}
          {myBracket && (
            <div className="rounded-xl border border-slate-700 bg-slate-900/60 px-3 py-3 space-y-2">
              <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Per-Round Estimate</p>
              <div className="flex items-center justify-between text-xs">
                <span className="text-emerald-400">Savings interest</span>
                <span className="font-semibold text-emerald-300">
                  +{formatMoney((Number(account?.savings_balance) || 0) * bankSavingsRate)}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-rose-400">Tier tax ({(Number(myBracket.rate || 0) * 100).toFixed(1)}% × 25% of wealth)</span>
                <span className="font-semibold text-rose-300">
                  -{formatMoney(myNetWorth * Number(myBracket.rate || 0) * 0.25)}
                </span>
              </div>
              {(() => {
                const savingsIncome = (Number(account?.savings_balance) || 0) * bankSavingsRate;
                const tierTax = myNetWorth * Number(myBracket.rate || 0) * 0.25;
                const net = savingsIncome - tierTax;
                return (
                  <div className="flex items-center justify-between text-xs border-t border-slate-700 pt-2">
                    <span className="text-slate-300 font-medium">Net</span>
                    <span className={`font-bold ${net >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>
                      {net >= 0 ? '+' : ''}{formatMoney(net)}
                    </span>
                  </div>
                );
              })()}
            </div>
          )}

          <p className="text-[11px] text-slate-500 px-1">The richer you get the more tax you pay. Your bracket is highlighted.</p>

          <div className="space-y-1.5">
            {[...taxBrackets].reverse().map((bracket, reverseIndex) => {
              const isActive = myBracket && (bracket.label || bracket.min_net_worth) === (myBracket.label || myBracket.min_net_worth);
              const totalBrackets = taxBrackets.length;
              const bracketIndex = totalBrackets - 1 - reverseIndex;
              const widthPct = 55 + (bracketIndex / Math.max(1, totalBrackets - 1)) * 45;
              return (
                <div
                  key={bracket.label || `${bracket.min_net_worth}-${bracket.max_net_worth}`}
                  className="mx-auto"
                  style={{ width: `${widthPct}%` }}
                >
                  <div
                    className={`rounded-lg border px-2 py-1.5 transition-all ${isActive ? 'border-fuchsia-400 bg-fuchsia-500/20 ring-1 ring-fuchsia-400/40' : 'border-slate-700 bg-slate-900/60'}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className={`text-[11px] font-semibold truncate ${isActive ? 'text-fuchsia-200' : 'text-slate-400'}`}>
                        {bracket.label || `${formatMoney(bracket.min_net_worth)}+`}
                      </span>
                      <span className={`text-[11px] font-bold flex-shrink-0 ${isActive ? 'text-fuchsia-100' : 'text-slate-300'}`}>
                        {(Number(bracket.rate || 0) * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="mt-0.5 text-[10px] text-slate-500 truncate">
                      {formatMoney(bracket.min_net_worth)}
                      {bracket.max_net_worth != null ? ` – ${formatMoney(bracket.max_net_worth)}` : '+'}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );

  if (embedded) {
    return content;
  }

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-950/85 p-3 shadow-[0_10px_30px_rgba(2,6,23,0.35)]">
      {content}
    </section>
  );
}
