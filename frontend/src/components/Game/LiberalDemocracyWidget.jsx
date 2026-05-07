import { useMemo } from 'react';
import { useGameStore } from '../../hooks/useGameState';
import { formatMoney } from '../../utils/formatters';

export default function LiberalDemocracyWidget({ onOpen }) {
  const { myPlayerId, players, economy } = useGameStore();
  const me = players.find((p) => p.id === myPlayerId) || null;
  const market = economy?.market || {};
  const assets = market?.assets || {};
  const bankAccounts = economy?.bank?.players || economy?.bank?.accounts || {};
  const portfolio = me?.portfolio || {};
  const cyclePhase = market?.cycle?.phase || 'growth';
  const sentiment = Number(market?.sentiment || 0).toFixed(0);

  const portfolioValue = useMemo(() => {
    const stocks = Object.entries(portfolio.stocks || {}).reduce(
      (sum, [key, qty]) => sum + (Number(qty) || 0) * (Number(assets[key]?.price) || 0),
      0,
    );
    const crypto = Object.entries(portfolio.crypto || {}).reduce(
      (sum, [key, qty]) => sum + (Number(qty) || 0) * (Number(assets[key]?.price) || 0),
      0,
    );
    return stocks + crypto;
  }, [assets, portfolio]);

  const savings = Number(bankAccounts[String(me?.id)]?.savings_balance) || 0;

  return (
    <div className="rounded-xl border border-cyan-900/40 bg-slate-900/60 p-3 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-xs font-semibold text-cyan-300 uppercase tracking-wider">Liberal Democracy</h3>
        <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${cyclePhase === 'decay' ? 'bg-rose-950 text-rose-200' : 'bg-emerald-950 text-emerald-200'}`}>
          {cyclePhase === 'decay' ? 'Falling' : 'Rising'}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-1.5 text-xs">
        <div className="rounded-lg bg-slate-800/60 px-2 py-1.5">
          <p className="text-slate-500 text-[10px]">Market Mood</p>
          <p className="font-semibold text-white">{sentiment}/100</p>
        </div>
        <div className="rounded-lg bg-slate-800/60 px-2 py-1.5">
          <p className="text-slate-500 text-[10px]">Cash</p>
          <p className="font-semibold text-emerald-300">{formatMoney(me?.balance || 0)}</p>
        </div>
        <div className="rounded-lg bg-slate-800/60 px-2 py-1.5">
          <p className="text-slate-500 text-[10px]">Portfolio</p>
          <p className="font-semibold text-cyan-300">{formatMoney(portfolioValue)}</p>
        </div>
        <div className="rounded-lg bg-slate-800/60 px-2 py-1.5">
          <p className="text-slate-500 text-[10px]">Savings</p>
          <p className="font-semibold text-sky-300">{formatMoney(savings)}</p>
        </div>
      </div>

      <button
        type="button"
        onClick={onOpen}
        className="w-full rounded-lg border border-cyan-700/70 bg-cyan-950/30 px-3 py-2 text-xs font-semibold text-cyan-200 transition hover:border-cyan-500 hover:text-white"
      >
        Open Liberal Democracy Panel
      </button>
    </div>
  );
}
