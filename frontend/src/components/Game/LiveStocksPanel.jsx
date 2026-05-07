import { useMemo, useState } from 'react';
import { useGameStore } from '../../hooks/useGameState';
import { formatMoney } from '../../utils/formatters';

function Sparkline({ history, positive }) {
  if (!history || history.length < 2) return null;
  const prices = history.map((h) => Number(h.price) || 0).filter((p) => p > 0);
  if (prices.length < 2) return null;
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const span = Math.max(1, max - min);
  const w = 60;
  const h = 22;
  const coords = prices.map((price, i) => {
    const x = (i / Math.max(1, prices.length - 1)) * w;
    const y = h - ((price - min) / span) * (h - 4) - 2;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const color = positive ? '#34d399' : '#fb7185';
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-5 w-14 flex-shrink-0" role="img">
      <polyline
        points={coords.join(' ')}
        fill="none"
        stroke={color}
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function LiveStocksPanel() {
  const { economy } = useGameStore();
  const market = economy?.market || {};
  const assets = market?.assets || {};
  const corporations = (economy?.corporations?.by_id) || {};
  const [selected, setSelected] = useState(null);

  const assetList = useMemo(
    () => Object.values(assets)
      .filter((a) => a?.price > 0)
      .sort((a, b) => String(a?.label || a?.asset_key || '').localeCompare(String(b?.label || b?.asset_key || ''))),
    [assets],
  );

  const selectedAsset = selected ? assets[selected] : null;
  const selectedCorp = selectedAsset?.corporation_id ? corporations[selectedAsset.corporation_id] : null;

  const cyclePhase = market?.cycle?.phase || 'growth';
  const sentiment = Number(market?.sentiment || 72).toFixed(0);

  return (
    <div className="flex h-full flex-col gap-2 text-white">
      <div className="flex items-center justify-between gap-2 flex-shrink-0">
        <p className="text-[11px] font-bold uppercase tracking-[0.22em] text-cyan-300">Live Market</p>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-slate-400">Mood: <span className="text-white font-semibold">{sentiment}/100</span></span>
          <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${cyclePhase === 'decay' ? 'bg-rose-950 text-rose-200' : 'bg-emerald-950 text-emerald-200'}`}>
            {cyclePhase === 'decay' ? 'Falling' : 'Rising'}
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto space-y-1 pr-1 min-h-0">
        {assetList.map((asset) => {
          const delta = Number(asset?.price_change_last_round || asset?.change || 0);
          const positive = delta >= 0;
          const corp = asset.corporation_id ? corporations[asset.corporation_id] : null;
          const isSelected = selected === asset.asset_key;
          return (
            <button
              key={asset.asset_key}
              type="button"
              onClick={() => setSelected(isSelected ? null : asset.asset_key)}
              className={`w-full rounded-lg border px-2.5 py-1.5 text-left transition ${isSelected ? 'border-cyan-500 bg-cyan-950/30' : 'border-slate-700/60 bg-slate-900/50 hover:border-slate-600'}`}
            >
              <div className="flex items-center gap-2">
                {corp?.color_hex && (
                  <span
                    className="h-2 w-2 flex-shrink-0 rounded-full"
                    style={{ backgroundColor: corp.color_hex }}
                  />
                )}
                <span className="flex-1 truncate text-xs font-semibold text-slate-200">{asset.label || asset.asset_key}</span>
                <Sparkline history={asset.history} positive={positive} />
                <div className="text-right flex-shrink-0">
                  <div className="text-xs font-bold text-white">{formatMoney(asset.price)}</div>
                  <div className={`text-[10px] font-semibold ${positive ? 'text-emerald-300' : 'text-rose-300'}`}>
                    {positive ? '+' : ''}{(delta * 100).toFixed(1)}%
                  </div>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {selectedAsset && (
        <div className="flex-shrink-0 rounded-xl border border-slate-700 bg-slate-900/80 p-2.5 space-y-1.5">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs font-semibold text-white">{selectedAsset.label || selectedAsset.asset_key}</p>
            <p className="text-xs font-bold text-white">{formatMoney(selectedAsset.price)}</p>
          </div>
          {selectedCorp && (
            <div className="grid grid-cols-2 gap-1.5 text-[11px]">
              <span className="text-slate-400">Properties: <span className="text-slate-200">{selectedCorp.property_ids?.length || 0}</span></span>
              <span className="text-slate-400">Dividend: <span className="text-emerald-300">{((Number(selectedCorp.dividend_yield || 0)) * 100).toFixed(1)}%</span></span>
              <span className="text-slate-400">Rent income: <span className="text-amber-300">{formatMoney(selectedCorp.rent_income_last_round || 0)}</span></span>
              <span className="text-slate-400">Cash reserve: <span className="text-sky-300">{formatMoney(selectedCorp.cash_reserve || 0)}</span></span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
