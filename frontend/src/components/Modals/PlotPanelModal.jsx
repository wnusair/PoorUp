import { useMemo, useState } from 'react';
import { useGameStore } from '../../hooks/useGameState';
import { formatExactMoney, formatMoney } from '../../utils/formatters';

const TAB_OPTIONS = [
  { key: 'overview', label: 'Overview' },
  { key: 'organization', label: 'Organization' },
  { key: 'territories', label: 'Territories' },
  { key: 'operations', label: 'Operations' },
  { key: 'counterplay', label: 'Counterplay' },
];

function cardTone(active) {
  return active
    ? 'border-red-500/50 bg-red-500/10 text-red-100'
    : 'border-slate-700 bg-slate-950/70 text-slate-300 hover:border-slate-500 hover:text-white';
}

function TabButton({ active, label, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        'rounded-full border px-4 py-2 text-sm font-semibold transition',
        active ? 'border-red-400/60 bg-red-500/15 text-red-100' : 'border-slate-700 bg-slate-950/70 text-slate-300 hover:border-slate-500 hover:text-white',
      ].join(' ')}
    >
      {label}
    </button>
  );
}

function Metric({ label, value, tone = 'text-slate-100' }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
      <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">{label}</p>
      <p className={`mt-2 text-2xl font-semibold ${tone}`}>{value}</p>
    </div>
  );
}

function Section({ title, children, className = '' }) {
  return (
    <section className={`rounded-3xl border border-slate-800 bg-slate-950/60 p-5 ${className}`.trim()}>
      <p className="text-xs uppercase tracking-[0.24em] text-slate-500">{title}</p>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function selectValue(value) {
  return value == null ? '' : String(value);
}

function equalSplitContributors(actorId, supporterIds, cashCost) {
  const participants = [actorId, ...supporterIds.filter((value) => value !== actorId)];
  if (!participants.length || cashCost <= 0) {
    return [];
  }

  const share = Math.ceil((cashCost / participants.length) * 100) / 100;
  let remaining = cashCost;
  return participants.map((playerId, index) => {
    const amount = index === participants.length - 1 ? Number(remaining.toFixed(2)) : Math.min(share, Number(remaining.toFixed(2)));
    remaining -= amount;
    return { player_id: playerId, amount };
  });
}

export default function PlotPanelModal({
  onClose,
  onPlotStart,
  onPlotAction,
  onPlotJoin,
  onPlotLeave,
  onPlotCounterAction,
}) {
  const { social, players, properties, myPlayerId } = useGameStore();
  const plot = social?.plot || {};
  const me = players.find((player) => player.id === myPlayerId) || null;
  const [activeTab, setActiveTab] = useState('overview');
  const [actionType, setActionType] = useState('');
  const [counterActionType, setCounterActionType] = useState('');
  const [selectedRegion, setSelectedRegion] = useState('');
  const [selectedPropertyId, setSelectedPropertyId] = useState('');
  const [selectedPlayerId, setSelectedPlayerId] = useState('');
  const [selectedClusterId, setSelectedClusterId] = useState('');
  const [sourceRegion, setSourceRegion] = useState('');
  const [targetRegion, setTargetRegion] = useState('');
  const [useSharedFunding, setUseSharedFunding] = useState(false);
  const [selectedSupporterIds, setSelectedSupporterIds] = useState([]);
  const [statusMessage, setStatusMessage] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const playerById = useMemo(
    () => Object.fromEntries((players || []).map((player) => [player.id, player])),
    [players],
  );
  const coalitionMembers = useMemo(
    () => (plot?.coalition_member_ids || []).map((playerId) => playerById[playerId]).filter(Boolean),
    [plot?.coalition_member_ids, playerById],
  );
  const allProperties = useMemo(() => Object.values(properties || {}), [properties]);
  const plotMember = Boolean(plot?.member_ids?.includes(myPlayerId));
  const committedMember = Boolean(plot?.committed_member_ids?.includes(myPlayerId));
  const coalitionMember = Boolean(plot?.coalition_member_ids?.includes(myPlayerId));
  const invitePending = Boolean(plot?.join_invites?.[String(myPlayerId)]);
  const currentActionDef = (plot?.action_catalog || []).find((entry) => entry.action_type === actionType) || null;
  const currentCounterDef = (plot?.counter_action_catalog || []).find((entry) => entry.action_type === counterActionType) || null;

  const recruitablePlayers = useMemo(
    () => (plot?.recruitable_players || []).filter((entry) => entry.player_id !== myPlayerId),
    [myPlayerId, plot?.recruitable_players],
  );

  const targetPropertyOptions = useMemo(() => ({
    agitate_property: allProperties,
    sabotage_development: allProperties,
    attempt_seizure: plot?.legal_targets || [],
    fortify_property: plot?.seized_properties || [],
    defend_reintegration: plot?.seized_properties || [],
    labor_settlement: allProperties,
    security_subsidy: allProperties,
    reintegration_campaign: plot?.seized_properties || [],
  }), [allProperties, plot?.legal_targets, plot?.seized_properties]);

  const currentMode = useMemo(() => {
    if (!plot?.exists) {
      return me?.plot_can_found ? 'eligible_founder' : 'ineligible';
    }
    if (plotMember) {
      return plot?.public ? 'public_revolutionary' : 'underground_member';
    }
    if (plot?.public) {
      return 'public_counterplay';
    }
    return 'observer';
  }, [me?.plot_can_found, plot?.exists, plot?.public, plotMember]);

  const regionOptions = useMemo(
    () => Object.keys(plot?.regions || {}).sort((left, right) => left.localeCompare(right)),
    [plot?.regions],
  );

  async function runAction(handler, payload) {
    if (!handler) {
      return;
    }
    setIsSubmitting(true);
    setStatusMessage('');
    try {
      const result = await handler(payload);
      setStatusMessage(result?.summary || 'Action resolved.');
    } catch (error) {
      setStatusMessage(error?.message || 'Action failed.');
    } finally {
      setIsSubmitting(false);
    }
  }

  function buildOperationPayload(definition) {
    if (!definition) {
      return null;
    }
    const payload = { action_type: definition.action_type };
    switch (definition.target) {
      case 'region':
      case 'region_optional':
        if (selectedRegion) {
          payload.region = selectedRegion;
        }
        break;
      case 'property':
      case 'seized_property':
      case 'property_or_region':
        if (selectedPropertyId) {
          payload.property_id = Number(selectedPropertyId);
        }
        if (!selectedPropertyId && selectedRegion && definition.target === 'property_or_region') {
          payload.region = selectedRegion;
        }
        break;
      case 'player':
        if (selectedPlayerId) {
          payload.target_player_id = Number(selectedPlayerId);
        }
        break;
      case 'cluster':
        if (selectedClusterId) {
          payload.cluster_id = selectedClusterId;
        }
        break;
      case 'two_regions':
        if (sourceRegion) {
          payload.source_region = sourceRegion;
        }
        if (targetRegion) {
          payload.target_region = targetRegion;
        }
        break;
      default:
        break;
    }
    return payload;
  }

  function buildCounterPayload(definition) {
    const payload = buildOperationPayload(definition) || {};
    payload.action_type = definition?.action_type;
    if (definition?.cash_cost > 0) {
      payload.contributors = useSharedFunding
        ? equalSplitContributors(myPlayerId, selectedSupporterIds, definition.cash_cost)
        : [{ player_id: myPlayerId, amount: definition.cash_cost }];
    }
    if ((definition?.supporters_required || 0) > 0 && selectedSupporterIds.length > 0) {
      payload.supporter_ids = selectedSupporterIds;
    }
    return payload;
  }

  return (
    <div className="modal-overlay">
      <div className="modal-panel modal-panel--wide max-h-[92vh] overflow-y-auto border border-red-500/20 bg-slate-950 text-white">
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.28em] text-red-300">Plot Panel</p>
            <h2 className="mt-2 text-3xl font-extrabold text-white">
              {plot?.exists ? (plot.stage_name || 'Communist Plot') : 'Revolutionary Possibility'}
            </h2>
            <p className="mt-2 max-w-3xl text-sm text-slate-300">
              {currentMode === 'eligible_founder' && 'Hardship conditions are met. You can ignite the communist plot if you are ready to abandon normal landlord play.'}
              {currentMode === 'ineligible' && 'This panel tracks hardship, revolutionary pressure, and later coalition counterplay even before the plot becomes actionable.'}
              {currentMode === 'underground_member' && 'The faction is still underground. Build cells, generate support, and prepare a legal seizure target without exposing yourself too early.'}
              {currentMode === 'public_revolutionary' && 'The plot is now public. Hold territory, manage Heat, and survive long enough to defend a rival power.'}
              {currentMode === 'public_counterplay' && 'The plot is public. Relief, intelligence, security, blockades, and reintegration all route through this panel.'}
              {currentMode === 'observer' && 'The plot remains underground. You can still inspect hardship and destabilization signals from here.'}
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

        <div className="mb-6 flex flex-wrap gap-2">
          {TAB_OPTIONS.map((tab) => (
            <TabButton
              key={tab.key}
              active={activeTab === tab.key}
              label={tab.label}
              onClick={() => setActiveTab(tab.key)}
            />
          ))}
        </div>

        {statusMessage ? (
          <div className="mb-6 rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-100">
            {statusMessage}
          </div>
        ) : null}

        {activeTab === 'overview' && (
          <div className="space-y-5">
            <div className="grid gap-3 md:grid-cols-4">
              <Metric label="Stage" value={plot?.exists ? `${plot.stage || 0}` : 'Locked'} tone="text-red-200" />
              <Metric label="Support" value={formatMoney(plot?.support || 0)} tone="text-rose-200" />
              <Metric label="Supply" value={formatMoney(plot?.supply || 0)} tone="text-orange-200" />
              <Metric label="Heat" value={`${Math.round(Number(plot?.heat || 0))}`} tone={Number(plot?.heat || 0) >= 85 ? 'text-red-300' : 'text-amber-200'} />
            </div>

            <div className="grid gap-5 lg:grid-cols-[1.15fr_0.85fr]">
              <Section title="My Position">
                <div className="space-y-3 text-sm text-slate-200">
                  <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-lg font-semibold text-white">{me?.username || 'Player'}</p>
                        <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                          {me?.plot_role ? me.plot_role.replaceAll('_', ' ') : 'No active plot role'}
                        </p>
                      </div>
                      <span className={`rounded-full border px-3 py-1 text-xs font-bold uppercase tracking-[0.18em] ${cardTone(Boolean(me?.plot_can_found || plotMember || coalitionMember))}`}>
                        {currentMode.replaceAll('_', ' ')}
                      </span>
                    </div>
                    <div className="mt-4 grid gap-3 sm:grid-cols-3">
                      <div>
                        <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Hardship</p>
                        <p className="mt-1 text-xl font-semibold text-red-100">{me?.plot_hardship_score || 0}</p>
                      </div>
                      <div>
                        <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Triggers</p>
                        <p className="mt-1 text-xl font-semibold text-white">{me?.plot_hardship_trigger_count || 0}</p>
                      </div>
                      <div>
                        <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Defection Lock</p>
                        <p className="mt-1 text-xl font-semibold text-white">{me?.plot_defection_cooldown_until || 0}</p>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Hardship Reasons</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {(me?.plot_hardship_reasons || []).length === 0 ? (
                        <span className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-400">No qualifying hardship pressure right now</span>
                      ) : (
                        (me?.plot_hardship_reasons || []).map((reason) => (
                          <span key={reason} className="rounded-full border border-red-500/20 bg-red-500/10 px-3 py-1 text-xs text-red-100">
                            {reason}
                          </span>
                        ))
                      )}
                    </div>
                  </div>
                </div>
              </Section>

              <Section title="Strategic Summary">
                <div className="space-y-4 text-sm text-slate-200">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Control</p>
                      <p className="mt-1 text-2xl font-semibold text-white">{Number(plot?.control_percent || 0).toFixed(1)}%</p>
                    </div>
                    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Countdown</p>
                      <p className="mt-1 text-2xl font-semibold text-white">
                        {plot?.victory_countdown?.active
                          ? `${plot.victory_countdown.rounds_held}/${plot.victory_countdown.required_rounds}`
                          : plot?.victory_countdown?.countdown_eligible
                          ? 'Ready'
                          : 'Blocked'}
                      </p>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Current Threat State</p>
                    <p className="mt-2 text-sm text-slate-200">
                      {plot?.victory_countdown?.blocked_reason || 'No special countdown block is currently active.'}
                    </p>
                    <div className="mt-4 flex flex-wrap gap-2">
                      <span className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-200">
                        {plot?.member_ids?.length || 0} active members
                      </span>
                      <span className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-200">
                        {plot?.seized_property_ids?.length || 0} seized properties
                      </span>
                      <span className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-200">
                        {plot?.clusters?.length || 0} live clusters
                      </span>
                      <span className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-200">
                        {plot?.coalition_member_ids?.length || 0} coalition members
                      </span>
                    </div>
                  </div>
                </div>
              </Section>
            </div>
          </div>
        )}

        {activeTab === 'organization' && (
          <div className="space-y-5">
            <Section title="Membership">
              <div className="flex flex-wrap gap-2">
                {(plot?.member_ids || []).length === 0 ? (
                  <span className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-400">No active revolutionary members yet</span>
                ) : (
                  (plot?.member_ids || []).map((playerId) => {
                    const player = playerById[playerId];
                    const role = player?.plot_role || 'member';
                    return (
                      <div key={playerId} className="rounded-2xl border border-slate-700 bg-slate-900/60 px-4 py-3 text-sm text-slate-100">
                        <p className="font-semibold text-white">{player?.username || `Player ${playerId}`}</p>
                        <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{role.replaceAll('_', ' ')}</p>
                      </div>
                    );
                  })
                )}
              </div>
            </Section>

            <Section title="Available Membership Moves">
              <div className="flex flex-wrap gap-3">
                {!plot?.exists && me?.plot_can_found ? (
                  <button
                    type="button"
                    disabled={isSubmitting}
                    onClick={() => runAction(onPlotStart, {})}
                    className="rounded-2xl border border-red-500/40 bg-red-500/15 px-4 py-3 text-sm font-semibold text-red-100 transition hover:border-red-400 hover:bg-red-500/20 disabled:opacity-50"
                  >
                    Found The Plot
                  </button>
                ) : null}
                {invitePending || (plot?.public && !plotMember && !coalitionMember) ? (
                  <button
                    type="button"
                    disabled={isSubmitting}
                    onClick={() => runAction(onPlotJoin, { intent: 'accept' })}
                    className="rounded-2xl border border-red-500/40 bg-red-500/15 px-4 py-3 text-sm font-semibold text-red-100 transition hover:border-red-400 hover:bg-red-500/20 disabled:opacity-50"
                  >
                    {invitePending ? 'Accept Invitation' : 'Join Public Faction'}
                  </button>
                ) : null}
                {invitePending ? (
                  <button
                    type="button"
                    disabled={isSubmitting}
                    onClick={() => runAction(onPlotJoin, { intent: 'decline' })}
                    className="rounded-2xl border border-slate-700 bg-slate-900/70 px-4 py-3 text-sm font-semibold text-slate-200 transition hover:border-slate-500 hover:text-white disabled:opacity-50"
                  >
                    Decline Invitation
                  </button>
                ) : null}
                {plotMember ? (
                  <button
                    type="button"
                    disabled={isSubmitting}
                    onClick={() => runAction(onPlotJoin, { intent: 'contribute' })}
                    className="rounded-2xl border border-slate-700 bg-slate-900/70 px-4 py-3 text-sm font-semibold text-slate-200 transition hover:border-slate-500 hover:text-white disabled:opacity-50"
                  >
                    Make Contribution
                  </button>
                ) : null}
                {plotMember && !committedMember ? (
                  <button
                    type="button"
                    disabled={isSubmitting}
                    onClick={() => runAction(onPlotJoin, { intent: 'commit' })}
                    className="rounded-2xl border border-slate-700 bg-slate-900/70 px-4 py-3 text-sm font-semibold text-slate-200 transition hover:border-slate-500 hover:text-white disabled:opacity-50"
                  >
                    Commit To The Faction
                  </button>
                ) : null}
                {plotMember ? (
                  <button
                    type="button"
                    disabled={isSubmitting}
                    onClick={() => runAction(onPlotLeave, {})}
                    className="rounded-2xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm font-semibold text-amber-100 transition hover:border-amber-400 hover:bg-amber-500/15 disabled:opacity-50"
                  >
                    Defect From Plot
                  </button>
                ) : null}
              </div>
            </Section>

            <Section title="Recruitable Players">
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {(plot?.eligible_players || []).map((entry) => (
                  <div key={entry.player_id} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 text-sm text-slate-200">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-white">{entry.username}</p>
                        <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                          {entry.plot_role ? entry.plot_role.replaceAll('_', ' ') : entry.recruitable ? 'Recruitable' : 'Locked'}
                        </p>
                      </div>
                      <span className={`rounded-full border px-2 py-1 text-[11px] font-bold uppercase tracking-[0.16em] ${cardTone(entry.hardship_score >= 2)}`}>
                        H {entry.hardship_score}
                      </span>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {(entry.hardship_reasons || []).length === 0 ? (
                        <span className="rounded-full border border-slate-700 px-2 py-1 text-[11px] text-slate-400">No surfaced hardship reasons</span>
                      ) : (
                        (entry.hardship_reasons || []).slice(0, 3).map((reason) => (
                          <span key={`${entry.player_id}-${reason}`} className="rounded-full border border-slate-700 px-2 py-1 text-[11px] text-slate-200">
                            {reason}
                          </span>
                        ))
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </Section>
          </div>
        )}

        {activeTab === 'territories' && (
          <div className="space-y-5">
            <Section title="Seized Properties">
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {(plot?.seized_properties || []).length === 0 ? (
                  <p className="text-sm text-slate-400">No territory is under revolutionary control yet.</p>
                ) : (
                  (plot?.seized_properties || []).map((entry) => (
                    <div key={entry.property_id} className="rounded-2xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-50">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-white">{entry.property_name}</p>
                          <p className="text-xs uppercase tracking-[0.18em] text-red-200/80">{entry.region} • space {entry.board_position}</p>
                        </div>
                        <span className="rounded-full border border-red-400/30 px-2 py-1 text-[11px] font-bold uppercase tracking-[0.16em] text-red-100">
                          {entry.cluster_id || 'solo'}
                        </span>
                      </div>
                      <div className="mt-4 grid gap-2 sm:grid-cols-3">
                        <div>
                          <p className="text-[11px] uppercase tracking-[0.18em] text-red-200/70">Entrenchment</p>
                          <p className="mt-1 text-lg font-semibold text-white">{entry.entrenchment}</p>
                        </div>
                        <div>
                          <p className="text-[11px] uppercase tracking-[0.18em] text-red-200/70">Supply Yield</p>
                          <p className="mt-1 text-lg font-semibold text-white">{entry.supply_yield}</p>
                        </div>
                        <div>
                          <p className="text-[11px] uppercase tracking-[0.18em] text-red-200/70">Reintegration</p>
                          <p className="mt-1 text-lg font-semibold text-white">{entry.reintegration_progress}%</p>
                        </div>
                      </div>
                      <p className="mt-4 text-xs text-red-100/80">Board value {formatMoney(entry.current_value)}{entry.blockaded ? ' • Blockaded' : ''}</p>
                    </div>
                  ))
                )}
              </div>
            </Section>

            <Section title="Clusters And Targets">
              <div className="grid gap-4 lg:grid-cols-2">
                <div className="space-y-3">
                  <p className="text-sm font-semibold text-white">Clusters</p>
                  {(plot?.clusters || []).length === 0 ? (
                    <p className="text-sm text-slate-400">No live seized clusters yet.</p>
                  ) : (
                    (plot?.clusters || []).map((cluster) => (
                      <div key={cluster.cluster_id} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 text-sm text-slate-200">
                        <div className="flex items-center justify-between gap-3">
                          <p className="font-semibold text-white">{cluster.cluster_id}</p>
                          <span className={`rounded-full border px-2 py-1 text-[11px] font-bold uppercase tracking-[0.16em] ${cardTone(cluster.entrenched)}`}>
                            {cluster.entrenched ? 'Entrenched' : 'Loose'}
                          </span>
                        </div>
                        <p className="mt-2 text-xs text-slate-400">{cluster.region_names.join(' • ') || 'No region data'} • {cluster.size} tiles</p>
                        <p className="mt-2 text-xs text-slate-400">Avg entrenchment {cluster.avg_entrenchment} • Reintegration {cluster.reintegration_pressure}%</p>
                      </div>
                    ))
                  )}
                </div>

                <div className="space-y-3">
                  <p className="text-sm font-semibold text-white">Legal Seizure Targets</p>
                  {(plot?.legal_targets || []).length === 0 ? (
                    <p className="text-sm text-slate-400">No legal seizure targets are currently exposed.</p>
                  ) : (
                    (plot?.legal_targets || []).map((entry) => (
                      <div key={entry.property_id} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 text-sm text-slate-200">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="font-semibold text-white">{entry.property_name}</p>
                            <p className="text-xs uppercase tracking-[0.16em] text-slate-500">{entry.region} • owned by {entry.owner_name}</p>
                          </div>
                          <span className="rounded-full border border-slate-700 px-2 py-1 text-[11px] font-bold uppercase tracking-[0.16em] text-slate-100">
                            Score {entry.preview_score}
                          </span>
                        </div>
                        <p className="mt-3 text-xs text-slate-400">Agitation {entry.agitation}{entry.adjacent_to_control ? ' • Adjacent to control' : ''}</p>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </Section>
          </div>
        )}

        {activeTab === 'operations' && (
          <div className="space-y-5">
            <Section title="Plot Operations">
              {!plotMember ? (
                <p className="text-sm text-slate-400">Only active plot members can issue revolutionary operations.</p>
              ) : (
                <div className="space-y-4">
                  <div className="grid gap-4 lg:grid-cols-2">
                    <label className="block text-sm text-slate-300">
                      <span className="mb-2 block text-xs uppercase tracking-[0.18em] text-slate-500">Operation</span>
                      <select
                        value={actionType}
                        onChange={(event) => setActionType(event.target.value)}
                        className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
                      >
                        <option value="">Select an operation</option>
                        {(plot?.action_catalog || [])
                          .filter((entry) => entry.stage <= (plot?.stage || 0))
                          .map((entry) => (
                            <option key={entry.action_type} value={entry.action_type}>{entry.label}</option>
                          ))}
                      </select>
                    </label>
                    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 text-sm text-slate-200">
                      <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Current Action Cost</p>
                      <p className="mt-2 text-white">
                        {currentActionDef
                          ? Object.entries(currentActionDef.cost || {}).map(([key, value]) => `${value} ${key}`).join(' + ') || 'No direct cost'
                          : 'Select an operation to see its cost.'}
                      </p>
                      <p className="mt-2 text-xs text-slate-400">{currentActionDef?.description || 'Plot actions are validated server-side and still require the right stage, targets, and timing.'}</p>
                    </div>
                  </div>

                  {currentActionDef?.target === 'region' || currentActionDef?.target === 'region_optional' || currentActionDef?.target === 'property_or_region' ? (
                    <label className="block text-sm text-slate-300">
                      <span className="mb-2 block text-xs uppercase tracking-[0.18em] text-slate-500">Region</span>
                      <select
                        value={selectedRegion}
                        onChange={(event) => setSelectedRegion(event.target.value)}
                        className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
                      >
                        <option value="">Select a region</option>
                        {regionOptions.map((region) => (
                          <option key={region} value={region}>{region}</option>
                        ))}
                      </select>
                    </label>
                  ) : null}

                  {['property', 'seized_property', 'property_or_region'].includes(currentActionDef?.target) ? (
                    <label className="block text-sm text-slate-300">
                      <span className="mb-2 block text-xs uppercase tracking-[0.18em] text-slate-500">Property</span>
                      <select
                        value={selectedPropertyId}
                        onChange={(event) => setSelectedPropertyId(event.target.value)}
                        className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
                      >
                        <option value="">Select a property</option>
                        {(targetPropertyOptions[currentActionDef?.action_type] || []).map((entry) => (
                          <option key={entry.property_id || entry.id} value={entry.property_id || entry.id}>
                            {entry.property_name || entry.name}
                          </option>
                        ))}
                      </select>
                    </label>
                  ) : null}

                  {currentActionDef?.target === 'player' ? (
                    <label className="block text-sm text-slate-300">
                      <span className="mb-2 block text-xs uppercase tracking-[0.18em] text-slate-500">Player</span>
                      <select
                        value={selectedPlayerId}
                        onChange={(event) => setSelectedPlayerId(event.target.value)}
                        className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
                      >
                        <option value="">Select a player</option>
                        {recruitablePlayers.map((entry) => (
                          <option key={entry.player_id} value={entry.player_id}>{entry.username}</option>
                        ))}
                      </select>
                    </label>
                  ) : null}

                  {currentActionDef?.target === 'cluster' ? (
                    <label className="block text-sm text-slate-300">
                      <span className="mb-2 block text-xs uppercase tracking-[0.18em] text-slate-500">Cluster</span>
                      <select
                        value={selectedClusterId}
                        onChange={(event) => setSelectedClusterId(event.target.value)}
                        className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
                      >
                        <option value="">Select a cluster</option>
                        {(plot?.clusters || []).map((cluster) => (
                          <option key={cluster.cluster_id} value={cluster.cluster_id}>{cluster.cluster_id}</option>
                        ))}
                      </select>
                    </label>
                  ) : null}

                  {currentActionDef?.target === 'two_regions' ? (
                    <div className="grid gap-4 md:grid-cols-2">
                      <label className="block text-sm text-slate-300">
                        <span className="mb-2 block text-xs uppercase tracking-[0.18em] text-slate-500">Source Region</span>
                        <select
                          value={sourceRegion}
                          onChange={(event) => setSourceRegion(event.target.value)}
                          className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
                        >
                          <option value="">Select source</option>
                          {regionOptions.map((region) => (
                            <option key={`source-${region}`} value={region}>{region}</option>
                          ))}
                        </select>
                      </label>
                      <label className="block text-sm text-slate-300">
                        <span className="mb-2 block text-xs uppercase tracking-[0.18em] text-slate-500">Target Region</span>
                        <select
                          value={targetRegion}
                          onChange={(event) => setTargetRegion(event.target.value)}
                          className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
                        >
                          <option value="">Select target</option>
                          {regionOptions.map((region) => (
                            <option key={`target-${region}`} value={region}>{region}</option>
                          ))}
                        </select>
                      </label>
                    </div>
                  ) : null}

                  <button
                    type="button"
                    disabled={!currentActionDef || isSubmitting}
                    onClick={() => runAction(onPlotAction, buildOperationPayload(currentActionDef))}
                    className="rounded-2xl border border-red-500/40 bg-red-500/15 px-4 py-3 text-sm font-semibold text-red-100 transition hover:border-red-400 hover:bg-red-500/20 disabled:opacity-50"
                  >
                    Execute Operation
                  </button>
                </div>
              )}
            </Section>
          </div>
        )}

        {activeTab === 'counterplay' && (
          <div className="space-y-5">
            <Section title="Coalition Status">
              <div className="flex flex-wrap gap-3 text-sm text-slate-200">
                <div className="rounded-2xl border border-slate-800 bg-slate-900/60 px-4 py-3">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Coalition Unlocked</p>
                  <p className="mt-1 text-lg font-semibold text-white">{plot?.coalition_unlocked ? 'Yes' : 'No'}</p>
                </div>
                <div className="rounded-2xl border border-slate-800 bg-slate-900/60 px-4 py-3">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Coalition Members</p>
                  <p className="mt-1 text-lg font-semibold text-white">{plot?.coalition_member_ids?.length || 0}</p>
                </div>
              </div>
              {plot?.public && !plotMember && !coalitionMember && plot?.coalition_unlocked ? (
                <button
                  type="button"
                  disabled={isSubmitting}
                  onClick={() => runAction(onPlotCounterAction, { action_type: 'join_coalition' })}
                  className="mt-4 rounded-2xl border border-cyan-500/40 bg-cyan-500/10 px-4 py-3 text-sm font-semibold text-cyan-100 transition hover:border-cyan-400 hover:bg-cyan-500/15 disabled:opacity-50"
                >
                  Join Anti-Revolution Coalition
                </button>
              ) : null}
            </Section>

            <Section title="Counter Actions">
              {!plot?.public ? (
                <p className="text-sm text-slate-400">Public counter-revolution tools only unlock after the plot becomes public.</p>
              ) : !coalitionMember ? (
                <p className="text-sm text-slate-400">Join the coalition to access pooled counter-actions.</p>
              ) : (
                <div className="space-y-4">
                  <div className="grid gap-4 lg:grid-cols-2">
                    <label className="block text-sm text-slate-300">
                      <span className="mb-2 block text-xs uppercase tracking-[0.18em] text-slate-500">Counter Action</span>
                      <select
                        value={counterActionType}
                        onChange={(event) => setCounterActionType(event.target.value)}
                        className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
                      >
                        <option value="">Select a counter-action</option>
                        {(plot?.counter_action_catalog || [])
                          .filter((entry) => entry.action_type !== 'join_coalition')
                          .map((entry) => (
                            <option key={entry.action_type} value={entry.action_type}>{entry.label}</option>
                          ))}
                      </select>
                    </label>
                    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 text-sm text-slate-200">
                      <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Coalition Cost</p>
                      <p className="mt-2 text-white">
                        {currentCounterDef
                          ? `${formatExactMoney(currentCounterDef.cash_cost || 0)}${currentCounterDef.supporters_required ? ` + ${currentCounterDef.supporters_required} supporter${currentCounterDef.supporters_required === 1 ? '' : 's'}` : ''}`
                          : 'Select a counter-action to see the pooled cost.'}
                      </p>
                      <p className="mt-2 text-xs text-slate-400">{currentCounterDef?.description || 'Counter-actions use pooled coalition cash and, when required, explicit supporter commitments.'}</p>
                    </div>
                  </div>

                  {currentCounterDef?.target === 'region' ? (
                    <label className="block text-sm text-slate-300">
                      <span className="mb-2 block text-xs uppercase tracking-[0.18em] text-slate-500">Region</span>
                      <select
                        value={selectedRegion}
                        onChange={(event) => setSelectedRegion(event.target.value)}
                        className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
                      >
                        <option value="">Select a region</option>
                        {regionOptions.map((region) => (
                          <option key={region} value={region}>{region}</option>
                        ))}
                      </select>
                    </label>
                  ) : null}

                  {['property', 'seized_property'].includes(currentCounterDef?.target) ? (
                    <label className="block text-sm text-slate-300">
                      <span className="mb-2 block text-xs uppercase tracking-[0.18em] text-slate-500">Property</span>
                      <select
                        value={selectedPropertyId}
                        onChange={(event) => setSelectedPropertyId(event.target.value)}
                        className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
                      >
                        <option value="">Select a property</option>
                        {(targetPropertyOptions[currentCounterDef?.action_type] || []).map((entry) => (
                          <option key={entry.property_id || entry.id} value={entry.property_id || entry.id}>
                            {entry.property_name || entry.name}
                          </option>
                        ))}
                      </select>
                    </label>
                  ) : null}

                  {currentCounterDef?.target === 'cluster' ? (
                    <label className="block text-sm text-slate-300">
                      <span className="mb-2 block text-xs uppercase tracking-[0.18em] text-slate-500">Cluster</span>
                      <select
                        value={selectedClusterId}
                        onChange={(event) => setSelectedClusterId(event.target.value)}
                        className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
                      >
                        <option value="">Select a cluster</option>
                        {(plot?.clusters || []).map((cluster) => (
                          <option key={cluster.cluster_id} value={cluster.cluster_id}>{cluster.cluster_id}</option>
                        ))}
                      </select>
                    </label>
                  ) : null}

                  {(currentCounterDef?.cash_cost || 0) > 0 ? (
                    <label className="flex items-center gap-3 rounded-2xl border border-slate-800 bg-slate-900/60 px-4 py-3 text-sm text-slate-200">
                      <input
                        type="checkbox"
                        checked={useSharedFunding}
                        onChange={(event) => setUseSharedFunding(event.target.checked)}
                        className="h-4 w-4 rounded border-slate-600 bg-slate-950 text-red-500"
                      />
                      Split the cash cost evenly across selected coalition supporters
                    </label>
                  ) : null}

                  {(currentCounterDef?.supporters_required || 0) > 0 || useSharedFunding ? (
                    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                      <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Coalition Supporters</p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {coalitionMembers.filter((player) => player.id !== myPlayerId).map((player) => {
                          const checked = selectedSupporterIds.includes(player.id);
                          return (
                            <label key={player.id} className="inline-flex items-center gap-2 rounded-full border border-slate-700 px-3 py-2 text-xs text-slate-200">
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={(event) => {
                                  setSelectedSupporterIds((current) => {
                                    if (event.target.checked) {
                                      return [...current, player.id];
                                    }
                                    return current.filter((value) => value !== player.id);
                                  });
                                }}
                                className="h-3.5 w-3.5 rounded border-slate-600 bg-slate-950 text-red-500"
                              />
                              {player.username}
                            </label>
                          );
                        })}
                      </div>
                    </div>
                  ) : null}

                  <button
                    type="button"
                    disabled={!currentCounterDef || isSubmitting}
                    onClick={() => runAction(onPlotCounterAction, buildCounterPayload(currentCounterDef))}
                    className="rounded-2xl border border-cyan-500/40 bg-cyan-500/10 px-4 py-3 text-sm font-semibold text-cyan-100 transition hover:border-cyan-400 hover:bg-cyan-500/15 disabled:opacity-50"
                  >
                    Execute Counter Action
                  </button>
                </div>
              )}
            </Section>
          </div>
        )}
      </div>
    </div>
  );
}