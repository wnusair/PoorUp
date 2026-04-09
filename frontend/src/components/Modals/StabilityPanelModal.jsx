import { useEffect, useMemo, useState } from 'react';
import HelpTooltip from '../Common/HelpTooltip';
import { useGameStore } from '../../hooks/useGameState';
import { calculateNetWorth, formatExactMoney, formatMoney } from '../../utils/formatters';
import { getGrievanceLabel, getIncidentLabel, getLobbyTargetLabel, humanizeSocialToken } from '../../utils/socialCopy';

const TAB_OPTIONS = [
  { key: 'overview', label: 'Overview' },
  { key: 'player_breakdown', label: 'Player Breakdown' },
  { key: 'negotiation', label: 'Negotiation' },
];

const SEVERITY_LABELS = {
  protest: 'Protest',
  strike: 'Strike',
  uprising: 'Uprising',
  revolution: 'Revolution',
};

const SEVERITY_STYLES = {
  protest: 'border-amber-500/40 bg-amber-500/10 text-amber-200',
  strike: 'border-orange-500/40 bg-orange-500/10 text-orange-200',
  uprising: 'border-red-500/40 bg-red-500/10 text-red-200',
  revolution: 'border-rose-500/40 bg-rose-500/10 text-rose-200',
};

const WATCH_STATE_STYLES = {
  active_incident: 'border-red-500/30 bg-red-500/10 text-red-200',
  critical_watch: 'border-amber-500/30 bg-amber-500/10 text-amber-200',
  watchlist: 'border-cyan-500/30 bg-cyan-500/10 text-cyan-200',
  stable: 'border-slate-700 bg-slate-900/70 text-slate-300',
};

const INCIDENT_THRESHOLDS = {
  protest: 50,
  strike: 65,
  uprising: 80,
  revolution: 90,
};

function percent(value) {
  const number = Number(value) || 0;
  return Math.max(0, Math.min(100, Math.round(number)));
}

function severityWeight(incidentType) {
  return {
    revolution: 4,
    uprising: 3,
    strike: 2,
    protest: 1,
  }[incidentType] || 0;
}

function humanize(value) {
  return humanizeSocialToken(value);
}

function ownerLabel(ownerId, formerOwnerId, playerById) {
  if (ownerId === 'proletariat_union' || formerOwnerId != null) {
    return 'Proletariat Union';
  }
  if (ownerId == null) {
    return 'Unowned';
  }
  return playerById[ownerId]?.username || `Owner ${ownerId}`;
}

function sortPropertyPressure(left, right) {
  const severityDelta = severityWeight(right.incident_type) - severityWeight(left.incident_type);
  if (severityDelta !== 0) {
    return severityDelta;
  }
  return (Number(right.tension) || 0) - (Number(left.tension) || 0);
}

function dedupeLabels(labels, limit = 4) {
  return [...new Set((labels || []).filter(Boolean))].slice(0, limit);
}

function etaLabel(value, incidentType) {
  if (incidentType) {
    const rounds = Number(value) || 0;
    if (rounds <= 0) {
      return 'Cooling';
    }
    if (rounds === 1) {
      return '1 round';
    }
    if (rounds === 2) {
      return '2 rounds';
    }
    return '3+ rounds';
  }

  if (value == null) {
    return 'Cooling';
  }

  const rounds = Number(value) || 0;
  if (rounds <= 0) {
    return 'Cooling';
  }
  if (rounds === 1) {
    return '1 round';
  }
  if (rounds === 2) {
    return '2 rounds';
  }
  return '3+ rounds';
}

function nextStateLabel(property) {
  if (property.incident_type) {
    return humanize(property.incident_type);
  }
  if (property.next_state) {
    return humanize(property.next_state);
  }

  const tension = Number(property.tension) || 0;
  if (tension >= INCIDENT_THRESHOLDS.revolution) {
    return 'Revolution Candidate';
  }
  if (tension >= INCIDENT_THRESHOLDS.uprising) {
    return 'Uprising';
  }
  if (tension >= INCIDENT_THRESHOLDS.strike) {
    return 'Strike';
  }
  if (tension >= INCIDENT_THRESHOLDS.protest) {
    return 'Protest';
  }
  return humanize(property.watch_state || 'watchlist');
}

function formatLobbyTargets(targets = []) {
  const normalizedTargets = dedupeLabels(targets.map((target) => getLobbyTargetLabel(target)), 3);
  return normalizedTargets.length > 0 ? normalizedTargets.join(' • ') : 'No dedicated lobby route surfaced';
}

function projectedReliefLabel(incident) {
  const target = Number(incident.negotiation_target) || 0;
  const committed = Number(incident.negotiation_committed) || 0;
  const coverage = target > 0 ? (committed / target) : 0;

  if (coverage >= 1.5) {
    return 'Max local relief funded: de-escalation pressure is already capped this round.';
  }
  if (coverage >= 1.0) {
    return 'Full coverage this round: tension -20, one-step de-escalation if eligible, and spread blocked.';
  }
  if (coverage >= 0.5) {
    return 'Partial coverage this round: tension -10 and one round shaved off the incident clock.';
  }
  return 'First funding threshold: reach 50% coverage for immediate tension and duration relief.';
}

function MetricCard({ label, value, tone = 'text-slate-100', tooltip = '' }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
      <p className="inline-flex items-center gap-1 text-[11px] uppercase tracking-[0.24em] text-slate-500">
        <span>{label}</span>
        {tooltip ? <HelpTooltip content={tooltip} label={`${label} help`} /> : null}
      </p>
      <p className={`mt-2 text-2xl font-semibold ${tone}`}>{value}</p>
    </div>
  );
}

function TabButton({ active, label, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        'rounded-full border px-4 py-2 text-sm font-semibold transition',
        active
          ? 'border-cyan-400/50 bg-cyan-500/15 text-cyan-100'
          : 'border-slate-700 bg-slate-900/70 text-slate-300 hover:border-slate-500 hover:text-white',
      ].join(' ')}
    >
      {label}
    </button>
  );
}

function PropertyDetailPanel({ property }) {
  if (!property) {
    return (
      <section className="rounded-3xl border border-slate-800 bg-slate-950/60 p-5">
        <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Property Breakdown</p>
        <p className="mt-4 text-sm text-slate-400">
          Select a property to inspect the exact instability drivers, owner exposure, and response options.
        </p>
      </section>
    );
  }

  const statusKey = property.incident_type || property.watch_state || 'stable';
  const statusLabel = property.incident_type
    ? SEVERITY_LABELS[property.incident_type] || getIncidentLabel(property.incident_type)
    : humanize(statusKey);
  const statusStyle = property.incident_type
    ? (SEVERITY_STYLES[property.incident_type] || WATCH_STATE_STYLES.stable)
    : (WATCH_STATE_STYLES[statusKey] || WATCH_STATE_STYLES.stable);
  const lobbyBacklash = property.hostile_lobby_targets || [];
  const recommendedActions = property.recommended_actions || [];

  return (
    <section className="rounded-3xl border border-slate-800 bg-slate-950/60 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Property Breakdown</p>
          <h3 className="mt-2 text-lg font-semibold text-slate-100">{property.property_name}</h3>
          <p className="mt-1 text-sm text-slate-400">
            {property.owner_name} • {property.region || 'Unassigned'}
            {property.board_position != null ? ` • space ${property.board_position}` : ''}
          </p>
        </div>
        <span className={`rounded-full border px-3 py-1 text-xs font-bold uppercase tracking-[0.18em] ${statusStyle}`}>
          {statusLabel}
        </span>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <MetricCard label="Property Pressure" tooltip="How close this property is to a protest, strike, uprising, or takeover." value={`${percent(property.tension)}%`} tone={percent(property.tension) >= 80 ? 'text-rose-300' : 'text-slate-100'} />
        <MetricCard label="Area Pressure" tooltip="How unstable the wider owner-and-region area is. High area pressure makes nearby trouble more likely to spread." value={`${percent(property.territory_instability)}%`} tone={percent(property.territory_instability) >= 75 ? 'text-orange-300' : 'text-slate-100'} />
        <MetricCard label="Development" value={String(Number(property.dev_level) || 0)} />
        <MetricCard label="Current Value" value={formatMoney(property.current_value || 0)} />
      </div>

      {property.former_owner_name && property.owner_name === 'Proletariat Union' && (
        <div className="mt-4 rounded-2xl border border-cyan-400/20 bg-cyan-500/10 p-4 text-sm text-cyan-100">
          Former private owner: <span className="font-semibold">{property.former_owner_name}</span>
          {property.reintegration_progress != null ? ` • Reintegration ${percent(property.reintegration_progress)}%` : ''}
        </div>
      )}

      <div className="mt-5 space-y-4">
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-slate-500">Why this area is heating up</p>
          <div className="mt-3 space-y-2">
            {(property.reason_breakdown || []).length === 0 && (
              <p className="text-sm text-slate-400">No dominant instability drivers are currently surfaced for this property.</p>
            )}
            {(property.reason_breakdown || []).map((reason) => (
              <div key={`${property.property_id}-${reason.key}`} className="rounded-2xl border border-slate-800 bg-slate-900/70 p-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-slate-100">{reason.key ? getGrievanceLabel(reason.key) : (reason.label || humanize(reason.key))}</p>
                  <span className="text-xs font-semibold text-slate-400">+{Number(reason.points || 0).toFixed(1)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {lobbyBacklash.length > 0 && (
          <div>
            <p className="text-xs uppercase tracking-[0.22em] text-slate-500">Harmful Policy Pressure</p>
            <div className="mt-3 space-y-2">
              {lobbyBacklash.map((target) => (
                <div key={`${property.property_id}-${target.target}`} className="rounded-2xl border border-rose-500/20 bg-rose-500/10 p-3 text-sm text-rose-100">
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-semibold">{target.label}</span>
                    <span className="text-xs font-semibold text-rose-200">+{Number(target.points || 0).toFixed(1)}</span>
                  </div>
                  <p className="mt-1 text-xs text-rose-200/80">
                    {formatMoney(target.contribution || 0)} committed into a {formatMoney(target.pool_total || 0)} pool.
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-slate-500">Best next moves</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {recommendedActions.length === 0 && (
              <span className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-400">No direct response surfaced</span>
            )}
            {recommendedActions.map((action) => (
              <span key={`${property.property_id}-${action.type}-${action.label}`} className="rounded-full border border-slate-700 bg-slate-900/70 px-3 py-1 text-xs text-slate-200">
                {action.label}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

export default function StabilityPanelModal({ onClose, onSubmitNegotiation, onApplyEmergencyReform }) {
  const { social, properties, players, myPlayerId, economy } = useGameStore();
  const [drafts, setDrafts] = useState({});
  const [activeTab, setActiveTab] = useState('overview');
  const [selectedPlayerId, setSelectedPlayerId] = useState(null);
  const [selectedPropertyId, setSelectedPropertyId] = useState(null);

  const playerById = useMemo(
    () => Object.fromEntries((players || []).map((player) => [player.id, player])),
    [players],
  );

  const propertyList = useMemo(() => Object.values(properties || {}), [properties]);

  const propertiesById = useMemo(
    () => Object.fromEntries(propertyList.map((property) => [property.id, property])),
    [propertyList],
  );

  const propertyEntries = useMemo(
    () => Object.values(social?.properties || {})
      .map((entry) => {
        const propertyId = Number(entry?.property_id ?? 0);
        const property = propertiesById[propertyId] || {};
        const ownerId = property.owner_id ?? entry.owner_id ?? null;
        const formerOwnerId = entry.former_owner_id ?? property.social_former_owner_id ?? null;

        return {
          ...property,
          ...entry,
          property_id: propertyId,
          property_name: property.name || `Property #${propertyId}`,
          board_position: property.board_position ?? null,
          region: entry.region || property.region || 'Unassigned',
          owner_id: ownerId,
          owner_name: ownerLabel(ownerId, formerOwnerId, playerById),
          former_owner_id: formerOwnerId,
          former_owner_name: formerOwnerId != null ? ownerLabel(formerOwnerId, null, playerById) : null,
          tension: Number(entry.tension) || 0,
          territory_instability: Number(entry.territory_instability) || 0,
          dev_level: Number(property.dev_level ?? 0) || 0,
          current_value: Number(property.current_value ?? property.base_price ?? 0) || 0,
          reason_breakdown: Array.isArray(entry.reason_breakdown) ? entry.reason_breakdown : [],
          recommended_actions: Array.isArray(entry.recommended_actions) ? entry.recommended_actions : [],
          recommended_lobby_targets: Array.isArray(entry.recommended_lobby_targets) ? entry.recommended_lobby_targets : [],
          hostile_lobby_targets: Array.isArray(entry.hostile_lobby_targets) ? entry.hostile_lobby_targets : [],
          eta_to_next_threshold: entry.eta_to_next_threshold == null ? null : Number(entry.eta_to_next_threshold),
          next_state: entry.next_state || null,
          spread_block_active: Boolean(entry.spread_block_active),
        };
      })
      .sort(sortPropertyPressure),
    [playerById, propertiesById, social?.properties],
  );

  const propertyEntriesById = useMemo(
    () => Object.fromEntries(propertyEntries.map((entry) => [entry.property_id, entry])),
    [propertyEntries],
  );

  const incidents = useMemo(
    () => [...(social?.active_incidents || [])]
      .map((incident) => {
        const property = propertyEntriesById[Number(incident.property_id)] || {};

        return {
          ...property,
          ...incident,
          property_id: Number(incident.property_id),
          property_name: property.property_name || `Property #${incident.property_id}`,
          current_owner_name: property.owner_name || 'Unowned',
          recommended_lobby_targets: Array.isArray(incident.recommended_lobby_targets)
            ? incident.recommended_lobby_targets
            : (property.recommended_lobby_targets || []),
          eta_to_next_threshold: incident.eta_to_next_threshold ?? property.eta_to_next_threshold ?? null,
        };
      })
      .sort(sortPropertyPressure),
    [propertyEntriesById, social?.active_incidents],
  );

  const territories = useMemo(
    () => [...(social?.territories || [])]
      .map((territory) => ({
        ...territory,
        owner_name: territory.owner_name || ownerLabel(territory.owner_id, null, playerById),
        property_ids: Array.isArray(territory.property_ids) ? territory.property_ids : [],
        dominant_grievances: Array.isArray(territory.dominant_grievances) ? territory.dominant_grievances : [],
      }))
      .sort((left, right) => (Number(right.territory_instability) || 0) - (Number(left.territory_instability) || 0)),
    [playerById, social?.territories],
  );

  const riskyProperties = useMemo(
    () => propertyEntries.filter((entry) => entry.incident_type || entry.tension >= 35),
    [propertyEntries],
  );

  const defaultSelectedPlayerId = players.some((player) => player.id === myPlayerId)
    ? myPlayerId
    : players[0]?.id ?? null;

  useEffect(() => {
    if (selectedPlayerId == null || !players.some((player) => player.id === selectedPlayerId)) {
      setSelectedPlayerId(defaultSelectedPlayerId);
    }
  }, [defaultSelectedPlayerId, players, selectedPlayerId]);

  const playerSummaries = useMemo(
    () => (players || [])
      .map((player) => {
        const ownedProperties = propertyEntries.filter((entry) => entry.owner_id === player.id);
        const unionizedAssets = propertyEntries.filter((entry) => entry.former_owner_id === player.id && entry.owner_id !== player.id);
        const relevantProperties = [...ownedProperties, ...unionizedAssets].sort(sortPropertyPressure);
        const territoriesUnderPressure = territories
          .filter((territory) => territory.owner_id === player.id)
          .sort((left, right) => (Number(right.territory_instability) || 0) - (Number(left.territory_instability) || 0));

        const reasonTotals = {};
        for (const property of relevantProperties) {
          for (const reason of property.reason_breakdown || []) {
            const key = reason.key || reason.label;
            if (!key) {
              continue;
            }
            const existing = reasonTotals[key] || { key, label: reason.key ? getGrievanceLabel(reason.key) : (reason.label || humanize(reason.key)), points: 0 };
            existing.points += Number(reason.points) || 0;
            reasonTotals[key] = existing;
          }
        }

        return {
          ...player,
          net_worth: calculateNetWorth(player, propertyList),
          ownedProperties,
          unionizedAssets,
          relevantProperties,
          territoriesUnderPressure,
          territoryInstabilityTotal: territoriesUnderPressure.reduce((sum, territory) => sum + (Number(territory.territory_instability) || 0), 0),
          maxTerritoryInstability: territoriesUnderPressure.reduce((maxValue, territory) => Math.max(maxValue, Number(territory.territory_instability) || 0), 0),
          activeIncidentCount: relevantProperties.filter((entry) => entry.incident_type).length,
          topTerritories: territoriesUnderPressure.slice(0, 2),
          topReasons: Object.values(reasonTotals)
            .sort((left, right) => right.points - left.points)
            .slice(0, 3),
          recommendedResponses: dedupeLabels(
            relevantProperties.flatMap((entry) => (entry.recommended_actions || []).map((action) => action.label)),
          ),
        };
      })
      .sort((left, right) => right.territoryInstabilityTotal - left.territoryInstabilityTotal || right.net_worth - left.net_worth),
    [players, propertyEntries, propertyList, territories],
  );

  const selectedPlayerSummary = playerSummaries.find((player) => player.id === selectedPlayerId) || null;
  const selectedPlayerProperties = selectedPlayerSummary?.relevantProperties || [];

  useEffect(() => {
    const propertyIds = new Set(
      (activeTab === 'player_breakdown' ? selectedPlayerProperties : riskyProperties).map((entry) => entry.property_id),
    );

    if (propertyIds.size === 0) {
      if (selectedPropertyId != null) {
        setSelectedPropertyId(null);
      }
      return;
    }

    if (!propertyIds.has(selectedPropertyId)) {
      setSelectedPropertyId([...propertyIds][0]);
    }
  }, [activeTab, riskyProperties, selectedPlayerId, selectedPlayerProperties, selectedPropertyId]);

  const selectedOverviewProperty = propertyEntriesById[selectedPropertyId] || riskyProperties[0] || null;
  const selectedPlayerProperty = selectedPlayerProperties.find((entry) => entry.property_id === selectedPropertyId) || selectedPlayerProperties[0] || null;

  const flashpoint = social?.national_flashpoint?.next_likely_escalation || null;
  const hottestTerritory = social?.national_flashpoint?.hottest_territory || null;
  const myPlayer = players.find((player) => player.id === myPlayerId) || null;
  const isMinarchism = (economy?.gov_type || economy?.government_type) === 'minarchism';

  const openPropertyBreakdown = (property) => {
    if (!property) {
      return;
    }
    if (property.owner_id != null && playerById[property.owner_id]) {
      setSelectedPlayerId(property.owner_id);
    } else if (property.former_owner_id != null && playerById[property.former_owner_id]) {
      setSelectedPlayerId(property.former_owner_id);
    }
    setSelectedPropertyId(property.property_id);
  };

  const updateDraft = (propertyId, value) => {
    setDrafts((current) => ({ ...current, [propertyId]: value }));
  };

  const submitNegotiation = (incident) => {
    const rawValue = drafts[incident.property_id] ?? '';
    const amount = Number(rawValue);
    if (!Number.isFinite(amount) || amount <= 0 || !onSubmitNegotiation) {
      return;
    }
    onSubmitNegotiation({ property_id: incident.property_id, contribution: amount });
    setDrafts((current) => ({ ...current, [incident.property_id]: '' }));
  };

  const suggestedContribution = (incident) => {
    const target = Number(incident.negotiation_target) || 0;
    const committed = Number(incident.negotiation_committed) || 0;
    const coverageGoal = incident.incident_type === 'protest' ? 0.5 : 1.0;
    return Math.max(25, Math.ceil((target * coverageGoal) - committed));
  };

  const renderEmergencyActions = (incident) => {
    if (!isMinarchism || !onApplyEmergencyReform) {
      return null;
    }

    return (
      <div className="mt-3 flex flex-wrap gap-2">
        {incident.incident_type !== 'revolution' && (
          <button
            type="button"
            onClick={() => onApplyEmergencyReform({ reform_type: 'private_relief_contract', property_id: incident.property_id })}
            className="rounded-full border border-cyan-400/40 bg-cyan-500/10 px-3 py-1 text-xs font-semibold text-cyan-200 transition hover:border-cyan-300 hover:bg-cyan-500/20"
          >
            Private Relief Contract
          </button>
        )}
        <button
          type="button"
          onClick={() => onApplyEmergencyReform({ reform_type: 'tax_moratorium', property_id: incident.property_id })}
          className="rounded-full border border-amber-400/40 bg-amber-500/10 px-3 py-1 text-xs font-semibold text-amber-200 transition hover:border-amber-300 hover:bg-amber-500/20"
        >
          Tax Moratorium
        </button>
        <button
          type="button"
          onClick={() => onApplyEmergencyReform({ reform_type: 'property_rights_compact', property_id: incident.property_id, target_region: incident.region })}
          className="rounded-full border border-emerald-400/40 bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-200 transition hover:border-emerald-300 hover:bg-emerald-500/20"
        >
          Property Rights Compact
        </button>
      </div>
    );
  };

  const renderGrievanceMix = () => (
    <section className="rounded-3xl border border-slate-800 bg-slate-950/60 p-5">
      <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Main Causes Across The Board</p>
      <div className="mt-4 space-y-3">
        {Object.entries(social?.grievance_mix || {}).slice(0, 6).map(([key, value]) => (
          <div key={key}>
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>{getGrievanceLabel(key)}</span>
              <span>{percent(value)}</span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-800">
              <div className="h-full rounded-full bg-gradient-to-r from-sky-400 via-cyan-300 to-emerald-300" style={{ width: `${Math.min(100, percent(value))}%` }} />
            </div>
          </div>
        ))}
      </div>
    </section>
  );

  const renderOverviewTab = () => (
    <>
      <div className="space-y-6">
        <section className="rounded-3xl border border-slate-800 bg-slate-950/60 p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Flashpoint</p>
              <h3 className="mt-2 text-lg font-semibold text-slate-100">
                {hottestTerritory?.region || 'No dominant hotspot'}
              </h3>
              {hottestTerritory?.owner_name && (
                <p className="mt-1 text-sm text-slate-400">Pressure is centered on {hottestTerritory.owner_name}.</p>
              )}
            </div>

            {flashpoint?.property_id && (
              <div className="rounded-2xl border border-slate-800 bg-slate-900/80 px-4 py-3 text-right">
                <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Next Likely Escalation</p>
                <p className="mt-1 text-sm font-semibold text-slate-200">
                  {propertiesById[flashpoint.property_id]?.name || `Property #${flashpoint.property_id}`}
                </p>
                <p className="text-xs text-slate-400">
                  {percent(flashpoint.tension)} tension • {humanize(flashpoint.next_state || 'watchlist')}
                </p>
              </div>
            )}
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-3">
            {(territories || []).slice(0, 6).map((territory) => (
              <button
                key={territory.territory_key}
                type="button"
                onClick={() => {
                  if (territory.owner_id != null) {
                    setSelectedPlayerId(territory.owner_id);
                  }
                  if (territory.property_ids?.[0] != null) {
                    setSelectedPropertyId(territory.property_ids[0]);
                  }
                }}
                className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4 text-left transition hover:border-slate-600"
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-100">{territory.region || 'Unassigned'}</p>
                    <p className="mt-1 text-xs text-slate-400">Owner: {territory.owner_name}</p>
                  </div>
                  <span className="text-xs font-semibold text-slate-400">{percent(territory.territory_instability)} instability</span>
                </div>
                <p className="mt-2 text-xs text-slate-400">
                  {territory.active_incident_count} incident(s) • {territory.property_count || territory.property_ids?.length || 0} properties
                </p>
                <p className="mt-3 text-[11px] uppercase tracking-[0.18em] text-slate-500">
                  {(territory.dominant_grievances || []).slice(0, 2).map(getGrievanceLabel).join(' • ') || 'No main cause surfaced'}
                </p>
              </button>
            ))}
          </div>
        </section>

        <section className="rounded-3xl border border-slate-800 bg-slate-950/60 p-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Properties Under Pressure</p>
              <h3 className="mt-2 text-lg font-semibold text-slate-100">Who is closest to a protest, strike, uprising, or takeover</h3>
            </div>
            <p className="text-sm text-slate-400">Click a row to inspect the exact breakdown.</p>
          </div>

          <div className="mt-4 space-y-2">
            {riskyProperties.length === 0 && (
              <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-sm text-emerald-200">
                No properties are above the watchlist threshold right now.
              </div>
            )}

            {riskyProperties.map((property) => (
              <button
                key={property.property_id}
                type="button"
                onClick={() => openPropertyBreakdown(property)}
                className={[
                  'grid w-full gap-3 rounded-2xl border px-4 py-3 text-left transition',
                  selectedOverviewProperty?.property_id === property.property_id
                    ? 'border-cyan-400/50 bg-cyan-500/10'
                    : 'border-slate-800 bg-slate-900/70 hover:border-slate-600',
                  'sm:grid-cols-[1.3fr,0.8fr,0.85fr,0.85fr,0.8fr,0.8fr,1.15fr,1.15fr]',
                ].join(' ')}
              >
                <div>
                  <p className="text-sm font-semibold text-slate-100">{property.property_name}</p>
                  <p className="mt-1 text-xs text-slate-400">{property.owner_name} • {property.region || 'Unassigned'}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Property Pressure</p>
                  <p className="mt-1 text-sm text-slate-200">{percent(property.tension)}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Area Pressure</p>
                  <p className="mt-1 text-sm text-slate-200">{percent(property.territory_instability)}%</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Next State</p>
                  <p className="mt-1 text-sm text-slate-200">{nextStateLabel(property)}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">ETA</p>
                  <p className="mt-1 text-sm text-slate-200">{etaLabel(property.eta_to_next_threshold, property.incident_type)}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Main Cause</p>
                  <p className="mt-1 text-sm text-slate-200">
                    {property.reason_breakdown?.[0]?.key ? getGrievanceLabel(property.reason_breakdown[0].key) : (property.reason_breakdown?.[0]?.label || getGrievanceLabel(property.dominant_grievance || 'mixed_grievance'))}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Best Move</p>
                  <p className="mt-1 text-sm text-slate-200">
                    {property.recommended_actions?.[0]?.label || 'No direct response surfaced'}
                  </p>
                </div>
              </button>
            ))}
          </div>
        </section>
      </div>

      <div className="space-y-6">
        <PropertyDetailPanel property={selectedOverviewProperty} />
        {renderGrievanceMix()}
      </div>
    </>
  );

  const renderPlayerBreakdownTab = () => (
    <>
      <div className="space-y-6">
        <section className="rounded-3xl border border-slate-800 bg-slate-950/60 p-5">
          <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Player Breakdown</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {playerSummaries.map((player) => (
              <button
                key={player.id}
                type="button"
                onClick={() => setSelectedPlayerId(player.id)}
                className={[
                  'rounded-full border px-4 py-2 text-sm font-semibold transition',
                  selectedPlayerId === player.id
                    ? 'border-cyan-400/50 bg-cyan-500/15 text-cyan-100'
                    : 'border-slate-700 bg-slate-900/70 text-slate-300 hover:border-slate-500 hover:text-white',
                ].join(' ')}
              >
                {player.username}
              </button>
            ))}
          </div>
        </section>

        {selectedPlayerSummary && (
          <section className="rounded-3xl border border-slate-800 bg-slate-950/60 p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Selected Player</p>
                <h3 className="mt-2 text-lg font-semibold text-slate-100">{selectedPlayerSummary.username}</h3>
                <p className="mt-1 text-sm text-slate-400">Net worth {formatExactMoney(selectedPlayerSummary.net_worth)}</p>
              </div>
              <div className="flex flex-wrap gap-2 text-xs text-slate-300">
                {selectedPlayerSummary.topReasons.map((reason) => (
                  <span key={`${selectedPlayerSummary.id}-${reason.key}`} className="rounded-full border border-slate-700 bg-slate-900/70 px-3 py-1">
                    {reason.label}
                  </span>
                ))}
              </div>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard label="Territory Instability Total" value={String(Math.round(selectedPlayerSummary.territoryInstabilityTotal))} tone={selectedPlayerSummary.territoryInstabilityTotal >= 150 ? 'text-orange-300' : 'text-slate-100'} />
              <MetricCard label="Owned Properties Under Pressure" value={String(selectedPlayerSummary.ownedProperties.length)} />
              <MetricCard label="Unionized Assets" value={String(selectedPlayerSummary.unionizedAssets.length)} tone={selectedPlayerSummary.unionizedAssets.length > 0 ? 'text-cyan-200' : 'text-slate-100'} />
              <MetricCard label="Active Incidents" value={String(selectedPlayerSummary.activeIncidentCount)} tone={selectedPlayerSummary.activeIncidentCount > 0 ? 'text-amber-300' : 'text-slate-100'} />
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              {selectedPlayerSummary.recommendedResponses.length === 0 && (
                <span className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-400">No responses surfaced yet</span>
              )}
              {selectedPlayerSummary.recommendedResponses.map((label) => (
                <span key={`${selectedPlayerSummary.id}-${label}`} className="rounded-full border border-slate-700 bg-slate-900/70 px-3 py-1 text-xs text-slate-200">
                  {label}
                </span>
              ))}
            </div>
          </section>
        )}

        <div className="grid gap-6 xl:grid-cols-[0.95fr,1.05fr]">
          <section className="rounded-3xl border border-slate-800 bg-slate-950/60 p-5">
            <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Territories Under Pressure</p>
            <div className="mt-4 space-y-3">
              {(selectedPlayerSummary?.territoriesUnderPressure || []).length === 0 && (
                <p className="text-sm text-slate-400">No owner-region blocs are currently under visible pressure for this player.</p>
              )}
              {(selectedPlayerSummary?.territoriesUnderPressure || []).map((territory) => (
                <div key={territory.territory_key} className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-slate-100">{territory.region || 'Unassigned'}</p>
                      <p className="mt-1 text-xs text-slate-400">{territory.owner_name}</p>
                    </div>
                    <span className="text-xs font-semibold text-slate-400">{percent(territory.territory_instability)} instability</span>
                  </div>
                  <p className="mt-2 text-xs text-slate-400">
                    {territory.active_incident_count} incident(s) • {territory.property_count || territory.property_ids?.length || 0} properties
                  </p>
                  <p className="mt-3 text-[11px] uppercase tracking-[0.18em] text-slate-500">
                    {(territory.dominant_grievances || []).map(humanize).slice(0, 2).join(' • ') || 'No dominant grievance'}
                  </p>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-3xl border border-slate-800 bg-slate-950/60 p-5">
            <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Properties Under Pressure</p>
            <div className="mt-4 space-y-2">
              {selectedPlayerProperties.length === 0 && (
                <p className="text-sm text-slate-400">This player does not currently own or retain any tracked pressure assets.</p>
              )}
              {selectedPlayerProperties.map((property) => (
                <button
                  key={property.property_id}
                  type="button"
                  onClick={() => setSelectedPropertyId(property.property_id)}
                  className={[
                    'w-full rounded-2xl border px-4 py-3 text-left transition',
                    selectedPlayerProperty?.property_id === property.property_id
                      ? 'border-cyan-400/50 bg-cyan-500/10'
                      : 'border-slate-800 bg-slate-900/70 hover:border-slate-600',
                  ].join(' ')}
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-slate-100">{property.property_name}</p>
                      <p className="mt-1 text-xs text-slate-400">
                        {property.region || 'Unassigned'}
                        {property.owner_name === 'Proletariat Union' && property.former_owner_id === selectedPlayerSummary?.id ? ' • Lost to union' : ''}
                      </p>
                    </div>
                    <span className="text-xs font-semibold text-slate-300">{percent(property.tension)} tension</span>
                  </div>
                </button>
              ))}
            </div>
          </section>
        </div>
      </div>

      <div className="space-y-6">
        <PropertyDetailPanel property={selectedPlayerProperty} />
      </div>
    </>
  );

  const renderNegotiationTab = () => (
    <>
      <div className="space-y-6">
        <section className="rounded-3xl border border-slate-800 bg-slate-950/60 p-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Active Problems</p>
              <h3 className="mt-2 text-lg font-semibold text-slate-100">How to calm each problem</h3>
            </div>
            {myPlayer && (
              <p className="text-sm text-slate-400">
                Acting as <span className="font-semibold text-slate-200">{myPlayer.username}</span>
              </p>
            )}
          </div>

          <div className="mt-4 space-y-3">
            {incidents.length === 0 && (
              <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-sm text-emerald-200">
                No active incidents. Watch the flashpoint rail for properties approaching escalation.
              </div>
            )}

            {incidents.map((incident) => {
              const coverage = percent(
                ((Number(incident.negotiation_committed) || 0) / Math.max(1, Number(incident.negotiation_target) || 1)) * 100,
              );
              const draftValue = drafts[incident.property_id] ?? suggestedContribution(incident);
              const propertyStyle = SEVERITY_STYLES[incident.incident_type] || 'border-slate-700 bg-slate-900 text-slate-100';

              return (
                <div key={incident.incident_id || incident.property_id} className={`rounded-3xl border p-4 ${propertyStyle}`}>
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] font-bold uppercase tracking-[0.18em]">
                          {SEVERITY_LABELS[incident.incident_type] || getIncidentLabel(incident.incident_type)}
                        </span>
                        <span className="text-sm font-semibold text-slate-100">{incident.property_name}</span>
                      </div>
                      <p className="mt-2 text-sm text-slate-300">
                        {incident.region || 'Unassigned'} • property pressure {percent(incident.tension)} • main cause: {getGrievanceLabel(incident.dominant_grievance || 'mixed_grievance')}
                      </p>
                      <p className="mt-1 text-xs text-slate-400">
                        Holder: {incident.current_owner_name} • {incident.remaining_rounds || 0} round(s) remaining
                      </p>
                      <p className="mt-1 text-xs text-slate-400">Recommended lobby targets: {formatLobbyTargets(incident.recommended_lobby_targets)}</p>
                    </div>
                    {incident.former_owner_id != null && (
                      <div className="rounded-2xl border border-cyan-400/20 bg-cyan-500/10 px-3 py-2 text-right text-xs text-cyan-100">
                        <p className="font-semibold uppercase tracking-[0.18em]">Unionized</p>
                        <p className="mt-1 text-cyan-200">Reintegration {percent(incident.reintegration_progress)}%</p>
                      </div>
                    )}
                  </div>

                  <div className="mt-4 grid gap-4 lg:grid-cols-[1fr,auto] lg:items-end">
                    <div>
                      <div className="flex items-center justify-between text-xs text-slate-400">
                        <span>Relief funding progress</span>
                        <span>{coverage}%</span>
                      </div>
                      <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-800">
                        <div
                          className="h-full rounded-full bg-cyan-300 transition-all"
                          style={{ width: `${Math.min(100, coverage)}%` }}
                        />
                      </div>
                      <p className="mt-2 text-xs text-slate-400">
                        {formatMoney(incident.negotiation_committed || 0)} of {formatMoney(incident.negotiation_target || 0)} committed
                      </p>
                      <p className="mt-2 text-xs text-slate-300">What happens if you fund it now: {projectedReliefLabel(incident)}</p>
                      {incident.spread_block_active && (
                        <p className="mt-2 text-xs font-semibold text-cyan-100">This problem cannot spread this round.</p>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-2 lg:justify-end">
                      <input
                        value={draftValue}
                        onChange={(event) => updateDraft(incident.property_id, event.target.value)}
                        inputMode="decimal"
                        className="w-28 rounded-full border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-400"
                      />
                      <button
                        type="button"
                        onClick={() => submitNegotiation(incident)}
                        className="rounded-full border border-cyan-400/40 bg-cyan-500/10 px-4 py-2 text-sm font-semibold text-cyan-200 transition hover:border-cyan-300 hover:bg-cyan-500/20"
                      >
                        Contribute
                      </button>
                    </div>
                  </div>

                  {renderEmergencyActions(incident)}
                </div>
              );
            })}
          </div>
        </section>
      </div>

      <div className="space-y-6">
        {renderGrievanceMix()}

        <section className="rounded-3xl border border-slate-800 bg-slate-950/60 p-5">
          <p className="text-xs uppercase tracking-[0.24em] text-slate-500">How To Read This Screen</p>
          <div className="mt-4 space-y-3 text-sm text-slate-300">
            <p>
              Public anger is the whole-board pressure meter. Area pressure shows where that anger is collecting.
            </p>
            <p>
              If a rich owner keeps pushing harsh rules, the damage shows up here before the policy even fully pays off.
            </p>
            <p>
              Fully funding local relief shortens problems and can stop them from spreading, but they will come back if the root cause does not change.
            </p>
          </div>
        </section>
      </div>
    </>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 px-4 py-6 backdrop-blur-sm">
      <div className="flex h-full max-h-[90vh] w-full max-w-6xl flex-col overflow-hidden rounded-[28px] border border-slate-800 bg-slate-900 shadow-2xl shadow-black/40">
        <div className="flex items-start justify-between border-b border-slate-800 px-6 py-5">
          <div>
            <p className="text-[11px] uppercase tracking-[0.28em] text-slate-500">National Stability</p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-100">Stability Panel</h2>
            <p className="mt-1 text-sm text-slate-400">
              See where anger is building, why it is happening, and what will calm it down fastest.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-300 transition hover:border-slate-500 hover:text-white"
          >
            Close
          </button>
        </div>

        <div className="px-6 py-5">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              label="Public Anger"
              tooltip="The overall pressure level across the whole game. Higher anger means more chance of protests, strikes, and takeovers."
              value={`${percent(social?.overall_rage)}/100`}
              tone={percent(social?.overall_rage) >= 75 ? 'text-rose-300' : 'text-slate-100'}
            />
            <MetricCard
              label="Stability"
              tooltip="How steady the economy is overall. Low stability makes local trouble harder to contain."
              value={`${percent(social?.stability_percent)}%`}
              tone={percent(social?.stability_percent) <= 35 ? 'text-amber-300' : 'text-slate-100'}
            />
            <MetricCard
              label="Active Problems"
              tooltip="Properties already in protest, strike, uprising, or takeover state."
              value={String((social?.active_incidents || []).length)}
              tone={(social?.active_incidents || []).length > 0 ? 'text-orange-200' : 'text-emerald-200'}
            />
            <MetricCard
              label="Union Takeovers"
              tooltip="Properties no longer under private control because unrest escalated too far."
              value={String(Number(social?.unionized_property_count) || 0)}
              tone={Number(social?.unionized_property_count) > 0 ? 'text-cyan-200' : 'text-slate-100'}
            />
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            {TAB_OPTIONS.map((tab) => (
              <TabButton
                key={tab.key}
                active={activeTab === tab.key}
                label={tab.label}
                onClick={() => setActiveTab(tab.key)}
              />
            ))}
          </div>
        </div>

        <div className="grid gap-6 overflow-y-auto px-6 pb-6 lg:grid-cols-[1.25fr,0.85fr]">
          {activeTab === 'overview' && renderOverviewTab()}
          {activeTab === 'player_breakdown' && renderPlayerBreakdownTab()}
          {activeTab === 'negotiation' && renderNegotiationTab()}
        </div>
      </div>
    </div>
  );
}