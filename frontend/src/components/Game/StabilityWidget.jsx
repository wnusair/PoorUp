import { useGameStore } from '../../hooks/useGameState';

const INCIDENT_PRIORITY = {
  revolution: 5,
  uprising: 4,
  strike: 3,
  protest: 2,
};

function territoryStatus(territory, socialProperties = {}) {
  const entries = (territory?.property_ids || [])
    .map((propertyId) => socialProperties[String(propertyId)])
    .filter(Boolean);

  const highestIncident = entries
    .map((entry) => entry?.incident_type)
    .filter(Boolean)
    .sort((left, right) => (INCIDENT_PRIORITY[right] || 0) - (INCIDENT_PRIORITY[left] || 0))[0];

  if (highestIncident) {
    return {
      label: highestIncident.charAt(0).toUpperCase() + highestIncident.slice(1),
      tone: 'border-rose-500/40 bg-rose-500/10 text-rose-100',
    };
  }

  if (entries.some((entry) => entry?.watch_state === 'critical_watch')) {
    return {
      label: 'Unstable',
      tone: 'border-amber-500/40 bg-amber-500/10 text-amber-100',
    };
  }

  if (entries.some((entry) => entry?.watch_state === 'watchlist')) {
    return {
      label: 'Watchlist',
      tone: 'border-sky-500/40 bg-sky-500/10 text-sky-100',
    };
  }

  return {
    label: 'Stable',
    tone: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-100',
  };
}

export default function StabilityWidget() {
  const { social } = useGameStore();
  const topTerritories = [...(social?.territories || [])]
    .sort((left, right) => (Number(right?.territory_instability) || 0) - (Number(left?.territory_instability) || 0))
    .slice(0, 3);

  return (
    <div className="bg-gray-800 rounded-xl p-3 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Stability</h3>
        <span className="text-[11px] text-gray-500">Top 3 areas</span>
      </div>

      {topTerritories.length === 0 ? (
        <div className="rounded-lg border border-slate-700 bg-slate-900/80 px-3 py-3 text-xs text-slate-400">
          No instability hotspots are active right now.
        </div>
      ) : (
        <div className="space-y-2">
          {topTerritories.map((territory) => {
            const status = territoryStatus(territory, social?.properties || {});
            return (
              <div key={territory.territory_key} className="rounded-lg border border-slate-700 bg-slate-900/80 px-3 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-slate-100 truncate">{territory.region || 'Unassigned region'}</p>
                    <p className="mt-1 text-[11px] text-slate-400 truncate">{territory.owner_name || 'No owner'}</p>
                  </div>
                  <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${status.tone}`}>
                    {status.label}
                  </span>
                </div>

                <div className="mt-2 flex items-center justify-between text-xs text-slate-400">
                  <span>{Math.round(Number(territory.territory_instability) || 0)}% instability</span>
                  <span>{Number(territory.active_incident_count) || 0} incidents</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}