import { useMemo, useState } from 'react';
import { useGameStore } from '../../hooks/useGameState';
import { formatExactMoney, formatMoney } from '../../utils/formatters';
import HelpTooltip from '../Common/HelpTooltip';

const TAB_OPTIONS = [
  { key: 'overview', label: 'Overview' },
  { key: 'organization', label: 'Organization' },
  { key: 'territories', label: 'Territories' },
  { key: 'operations', label: 'Operations' },
  { key: 'counterplay', label: 'Counterplay' },
];

const GLOBAL_OPERATION_TYPES = new Set([
  'mutual_aid',
  'establish_safehouse',
  'seed_cell',
  'hide_assets',
  'stockpile_supply',
  'spread_to_adjacent_territory',
  'call_emergency_redistribution',
  'establish_regional_council',
  'increase_entrenchment',
  'redirect_supply_between_regions',
  'call_mass_action',
]);

const GLOBAL_COUNTER_TYPES = new Set([
  'relief_package',
  'intelligence_sweep',
  'blockade_cluster',
  'propaganda_counteroffensive',
]);

const ROLE_SUMMARIES = {
  sympathizer: {
    current: 'Can contribute to the faction and build trust inside the network.',
    next: 'Promotion to organizer unlocks plot operations and regional orders.',
    tooltip: 'Sympathizer: The entry-level role. Sympathizers cannot issue orders or coordinate actions, but they can make contributions to build up trust and eventually get promoted.',
  },
  organizer: {
    current: 'Can issue plot operations and coordinate regional work.',
    next: 'Promotion to committed member secures deeper faction authority.',
    tooltip: 'Organizer: A seasoned member who can issue global and regional plot operations. Organizers can invite new members and fully commit to the plot.',
  },
  committed_member: {
    current: 'Can fully commit to the faction and hold stronger command weight.',
    next: 'Promotion to cadre improves succession priority and command standing.',
    tooltip: 'Committed Member: A fully devoted operative. They hold stronger command weight and priority in the succession chain.',
  },
  cadre: {
    current: 'Provides top-tier command depth and succession strength.',
    next: 'This is the highest internal promotion tier.',
    tooltip: 'Cadre: The elite command layer. They have the highest succession priority and deeply influence the command structure.',
  },
  founder: {
    current: 'Founded the faction and usually anchors command and succession.',
    next: 'Commitment progression strengthens long-term command authority.',
    tooltip: 'Founder: The original creator of the plot. Usually anchors the entire command structure and has the ultimate authority unless replaced.',
  },
};

function formatRoleLabel(role) {
  return String(role || 'none').replaceAll('_', ' ');
}

function RoleBadge({ role }) {
  const summary = ROLE_SUMMARIES[role];
  const label = formatRoleLabel(role);
  if (!summary) return label;
  return (
    <span className="inline-flex items-center gap-1.5">
      {label}
      <HelpTooltip content={summary.tooltip} label={`${label} role info`} />
    </span>
  );
}

function getRoleSummary(entry) {
  const role = String(entry?.role || '');
  return ROLE_SUMMARIES[role] || {
    current: 'No faction role is active right now.',
    next: 'Join and contribute to unlock faction responsibilities.',
  };
}

function getPromotionProgressLabel(entry) {
  if (!entry?.next_role) {
    return '';
  }

  if (entry.role === 'sympathizer') {
    return `Promotion progress: ${entry.contribution_round_count || 0}/${entry.required_contribution_rounds || 0} contribution rounds.`;
  }

  if (entry.role === 'organizer' || entry.role === 'founder') {
    return `Commit progress: ${entry.contribution_round_count || 0}/${entry.required_contribution_rounds || 0} contribution rounds, ${entry.successful_actions_supported || 0}/${entry.required_successful_actions || 0} successful actions.`;
  }

  if (entry.role === 'committed_member') {
    const cadreTarget = Math.max(3, (entry.required_successful_actions || 0) + 1);
    return `Cadre progress: ${entry.successful_actions_supported || 0}/${cadreTarget} successful actions.`;
  }

  return '';
}

function buildFoundingRequirements(player) {
  const triggerCount = player?.plot_hardship_trigger_count || 0;
  const reasons = Array.isArray(player?.plot_hardship_reasons) ? player.plot_hardship_reasons : [];

  return [
    {
      label: `Hardship triggers ${triggerCount}/2`,
      met: Boolean(player?.plot_can_found),
    },
    ...reasons.slice(0, 2).map((reason) => ({
      label: reason,
      met: true,
    })),
  ];
}

function tabTone(active) {
  return active
    ? 'border-rose-300/70 bg-rose-200 text-slate-950'
    : 'border-slate-700 bg-slate-950/70 text-slate-300 hover:border-slate-500 hover:text-white';
}

function TabButton({ active, label, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        'rounded-full border px-4 py-2 text-sm font-semibold transition',
        tabTone(active),
      ].join(' ')}
    >
      {label}
    </button>
  );
}

function Section({ title, subtitle, children, className = '' }) {
  return (
    <section className={`rounded-[28px] border border-slate-800 bg-slate-950/60 p-5 ${className}`.trim()}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-slate-500">{title}</p>
          {subtitle ? <p className="mt-2 text-sm text-slate-400">{subtitle}</p> : null}
        </div>
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function Metric({ label, value, tone = 'text-white' }) {
  return (
    <div className="rounded-3xl border border-slate-800 bg-slate-950/80 p-4">
      <p className="text-[11px] uppercase tracking-[0.22em] text-slate-500">{label}</p>
      <p className={`mt-2 text-2xl font-semibold ${tone}`}>{value}</p>
    </div>
  );
}

function formatCost(definition) {
  if (!definition) {
    return 'No cost data';
  }
  if ((definition.cash_cost || 0) > 0) {
    return `${formatExactMoney(definition.cash_cost || 0)}${definition.supporters_required ? ` + ${definition.supporters_required} supporter${definition.supporters_required === 1 ? '' : 's'}` : ''}`;
  }
  const costEntries = Object.entries(definition.cost || {});
  if (!costEntries.length) {
    return 'No direct cost';
  }
  return costEntries.map(([key, value]) => `${value} ${key}`).join(' + ');
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

function ActionCard({
  definition,
  selection,
  onSelectionChange,
  onRun,
  disabled,
  regionOptions,
  clusters,
  buttonTone = 'btn-danger',
}) {
  const target = definition?.target;

  return (
    <div className="rounded-3xl border border-slate-800 bg-slate-900/70 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-base font-semibold text-white">{definition.label}</p>
          <p className="mt-1 text-sm text-slate-400">{definition.description}</p>
        </div>
        <span className="rounded-full border border-slate-700 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-200">
          {formatCost(definition)}
        </span>
      </div>

      <div className="mt-4 space-y-3">
        {(target === 'region' || target === 'region_optional') ? (
          <label className="block text-sm text-slate-300">
            <span className="mb-2 block text-xs uppercase tracking-[0.18em] text-slate-500">Region</span>
            <select
              value={selection.region || ''}
              onChange={(event) => onSelectionChange({ region: event.target.value })}
              className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
            >
              <option value="">Select a region</option>
              {regionOptions.map((region) => (
                <option key={region} value={region}>{region}</option>
              ))}
            </select>
          </label>
        ) : null}

        {target === 'cluster' ? (
          <label className="block text-sm text-slate-300">
            <span className="mb-2 block text-xs uppercase tracking-[0.18em] text-slate-500">Cluster</span>
            <select
              value={selection.cluster_id || ''}
              onChange={(event) => onSelectionChange({ cluster_id: event.target.value })}
              className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
            >
              <option value="">Select a cluster</option>
              {clusters.map((cluster) => (
                <option key={cluster.cluster_id} value={cluster.cluster_id}>{cluster.cluster_id}</option>
              ))}
            </select>
          </label>
        ) : null}

        {target === 'two_regions' ? (
          <div className="grid gap-3 md:grid-cols-2">
            <label className="block text-sm text-slate-300">
              <span className="mb-2 block text-xs uppercase tracking-[0.18em] text-slate-500">Source Region</span>
              <select
                value={selection.source_region || ''}
                onChange={(event) => onSelectionChange({ source_region: event.target.value })}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
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
                value={selection.target_region || ''}
                onChange={(event) => onSelectionChange({ target_region: event.target.value })}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
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
          disabled={disabled}
          onClick={onRun}
          className={`${buttonTone} btn-sm`}
        >
          Execute
        </button>
      </div>
    </div>
  );
}

function buildPayload(definition, selection) {
  const payload = { action_type: definition.action_type };
  if (definition.target === 'region' || definition.target === 'region_optional') {
    if (selection.region) {
      payload.region = selection.region;
    }
  }
  if (definition.target === 'cluster' && selection.cluster_id) {
    payload.cluster_id = selection.cluster_id;
  }
  if (definition.target === 'two_regions') {
    if (selection.source_region) {
      payload.source_region = selection.source_region;
    }
    if (selection.target_region) {
      payload.target_region = selection.target_region;
    }
  }
  return payload;
}

export default function PlotPanelModal({
  onClose,
  onPlotStart,
  onPlotAction,
  onPlotJoin,
  onPlotLeave,
  onPlotCounterAction,
}) {
  const { social, players, myPlayerId } = useGameStore();
  const plot = social?.plot || {};
  const me = players.find((player) => player.id === myPlayerId) || null;
  const [activeTab, setActiveTab] = useState('overview');
  const [statusMessage, setStatusMessage] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [operationSelections, setOperationSelections] = useState({});
  const [counterSelections, setCounterSelections] = useState({});
  const [shareCounterFunding, setShareCounterFunding] = useState(false);
  const [selectedSupporterIds, setSelectedSupporterIds] = useState([]);

  const playerById = useMemo(
    () => Object.fromEntries((players || []).map((player) => [player.id, player])),
    [players],
  );

  const regionOptions = useMemo(
    () => Object.keys(plot?.regions || {}).sort((left, right) => left.localeCompare(right)),
    [plot?.regions],
  );

  const plotMember = Boolean(plot?.member_ids?.includes(myPlayerId));
  const coalitionMember = Boolean(plot?.coalition_member_ids?.includes(myPlayerId));
  const committedMember = Boolean(plot?.committed_member_ids?.includes(myPlayerId));
  const invitePending = Boolean(plot?.join_invites?.[String(myPlayerId)]);
  const joinRequestPending = Boolean(plot?.join_requests?.[String(myPlayerId)]);
  const commandEntry = (plot?.command_chain || []).find((entry) => entry.player_id === myPlayerId) || null;
  const isCommander = Boolean(commandEntry?.can_manage_membership);
  const canIssueOrders = Boolean(commandEntry?.can_issue_orders || (plotMember && (me?.plot_role || '') !== 'sympathizer'));
  const coalitionSupporters = useMemo(
    () => (plot?.coalition_member_ids || []).map((playerId) => playerById[playerId]).filter((player) => player && player.id !== myPlayerId),
    [myPlayerId, playerById, plot?.coalition_member_ids],
  );

  const pendingJoinRequests = useMemo(
    () => Object.values(plot?.join_requests || {}).map((entry) => ({ ...entry, username: playerById[entry.player_id]?.username || `Player ${entry.player_id}` })),
    [playerById, plot?.join_requests],
  );

  const recruitablePlayers = useMemo(
    () => (plot?.recruitable_players || []).filter((entry) => entry.player_id !== myPlayerId),
    [myPlayerId, plot?.recruitable_players],
  );

  const organizationAction = useMemo(() => {
    if ((plot?.action_catalog || []).some((entry) => entry.action_type === 'recruit_publicly' && entry.stage <= (plot?.stage || 0)) && plot?.public) {
      return 'recruit_publicly';
    }
    if ((plot?.action_catalog || []).some((entry) => entry.action_type === 'recruit_sympathizer' && entry.stage <= (plot?.stage || 0))) {
      return 'recruit_sympathizer';
    }
    return null;
  }, [plot?.action_catalog, plot?.public, plot?.stage]);

  const organizerPromotionAction = useMemo(
    () => (plot?.action_catalog || []).find((entry) => entry.action_type === 'convert_to_organizer' && entry.stage <= (plot?.stage || 0)) || null,
    [plot?.action_catalog, plot?.stage],
  );

  const nextStagePanel = useMemo(() => {
    if (!plot?.exists) {
      return {
        title: 'Founding requirements',
        target: 'Underground Cell',
        requirements: buildFoundingRequirements(me),
      };
    }

    return {
      title: 'Next stage',
      target: plot?.next_stage?.stage_name || 'No further stage',
      requirements: plot?.next_stage?.requirements || [],
    };
  }, [me, plot]);

  const globalOperations = useMemo(
    () => (plot?.action_catalog || []).filter((entry) => GLOBAL_OPERATION_TYPES.has(entry.action_type) && entry.stage <= (plot?.stage || 0)),
    [plot?.action_catalog, plot?.stage],
  );

  const globalCounterActions = useMemo(
    () => (plot?.counter_action_catalog || []).filter((entry) => GLOBAL_COUNTER_TYPES.has(entry.action_type)),
    [plot?.counter_action_catalog],
  );

  async function runAction(handler, payload) {
    if (!handler) {
      return;
    }
    setStatusMessage('');
    setIsSubmitting(true);
    try {
      const result = await handler(payload);
      setStatusMessage(result?.summary || 'Action resolved.');
    } catch (error) {
      setStatusMessage(error?.message || 'Action failed.');
    } finally {
      setIsSubmitting(false);
    }
  }

  function updateOperationSelection(actionType, patch) {
    setOperationSelections((current) => ({
      ...current,
      [actionType]: {
        ...(current[actionType] || {}),
        ...patch,
      },
    }));
  }

  function updateCounterSelection(actionType, patch) {
    setCounterSelections((current) => ({
      ...current,
      [actionType]: {
        ...(current[actionType] || {}),
        ...patch,
      },
    }));
  }

  function buildCounterPayload(definition, selection) {
    const payload = buildPayload(definition, selection);
    if ((definition.cash_cost || 0) > 0) {
      payload.contributors = shareCounterFunding
        ? equalSplitContributors(myPlayerId, selectedSupporterIds, definition.cash_cost)
        : [{ player_id: myPlayerId, amount: definition.cash_cost }];
    }
    if ((definition.supporters_required || 0) > 0) {
      payload.supporter_ids = [myPlayerId, ...selectedSupporterIds];
    }
    return payload;
  }

  return (
    <div className="modal-overlay">
      <div className="modal-panel modal-panel--plot max-h-[94vh] overflow-y-auto border border-rose-500/20 bg-[#070716] text-white">
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.28em] text-rose-300">Plot Panel</p>
            <h2 className="mt-2 text-3xl font-extrabold text-white">
              {plot?.exists ? (plot.stage_name || 'Communist Plot') : 'Revolutionary Possibility'}
            </h2>
            <p className="mt-2 max-w-4xl text-sm text-slate-300">
              {plot?.exists
                ? 'This panel now handles leadership, join requests, region-wide operations, and coalition-wide counterplay. Property-specific actions should be taken directly from the property modal.'
                : 'Track hardship and founding readiness here. Once the plot exists, property-specific pressure and seizures move to the property modal.'}
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
          <div className="mb-6 rounded-3xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
            {statusMessage}
          </div>
        ) : null}

        {activeTab === 'overview' ? (
          <div className="space-y-5">
            <div className="grid gap-3 md:grid-cols-6">
              <div className="rounded-3xl border border-slate-800 bg-slate-950/80 p-4 md:col-span-2">
                <p className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Stage</p>
                <div className="mt-2 flex items-start justify-between gap-3">
                  <p className="text-2xl font-semibold text-rose-100">{plot?.exists ? `${plot.stage || 0}` : 'Locked'}</p>
                  <p className="text-right text-[11px] uppercase tracking-[0.18em] text-slate-400">{nextStagePanel.target}</p>
                </div>
                <div className="mt-3 space-y-2">
                  <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{nextStagePanel.title}</p>
                  {(nextStagePanel.requirements || []).length === 0 ? (
                    <p className="text-sm text-slate-400">No further stage requirements are active.</p>
                  ) : (
                    (nextStagePanel.requirements || []).map((requirement) => (
                      <p
                        key={requirement.label}
                        className={[
                          'text-[13px] leading-5',
                          requirement.met ? 'text-emerald-200' : 'text-slate-300',
                        ].join(' ')}
                      >
                        {requirement.met ? 'Ready: ' : 'Need: '}
                        {requirement.label}
                      </p>
                    ))
                  )}
                </div>
              </div>
              <Metric label="Support" value={formatMoney(plot?.support || 0)} tone="text-rose-200" />
              <Metric label="Supply" value={formatMoney(plot?.supply || 0)} tone="text-orange-200" />
              <Metric label="Heat" value={`${Math.round(Number(plot?.heat || 0))}`} tone={Number(plot?.heat || 0) >= 85 ? 'text-red-300' : 'text-amber-200'} />
              <Metric label="Control" value={`${Number(plot?.control_percent || 0).toFixed(1)}%`} tone="text-cyan-200" />
            </div>

            {plotMember && (
              <div className="grid gap-3 md:grid-cols-3">
                <div className="rounded-3xl border border-amber-900/60 bg-amber-950/20 p-4">
                  <p className="text-[11px] uppercase tracking-[0.22em] text-amber-400">Faction Treasury</p>
                  <p className="mt-2 text-2xl font-semibold text-white">{formatExactMoney(plot?.joint_account_balance || 0)}</p>
                  <p className="mt-1 text-xs text-amber-200/70">Pooled cash available for faction operations</p>
                </div>
                <div className="rounded-3xl border border-orange-900/60 bg-orange-950/20 p-4">
                  <p className="text-[11px] uppercase tracking-[0.22em] text-orange-400">Contribution Rate</p>
                  <p className="mt-2 text-2xl font-semibold text-white">{((Number(plot?.joint_account_contribution_rate || 0)) * 100).toFixed(0)}%</p>
                  <p className="mt-1 text-xs text-orange-200/70">Share of each member's contribution that pools here</p>
                </div>
                <div className="rounded-3xl border border-yellow-900/60 bg-yellow-950/20 p-4">
                  <p className="text-[11px] uppercase tracking-[0.22em] text-yellow-400">My Cash Contributed</p>
                  <p className="mt-2 text-2xl font-semibold text-white">
                    {formatExactMoney(
                      Object.values(plot?.joint_account_contributions || {}).reduce((sum, val) => sum + (Number(val) || 0), 0)
                    )}
                  </p>
                  <p className="mt-1 text-xs text-yellow-200/70">Total pooled from all members this game</p>
                </div>
              </div>
            )}

            {(isCommander || me?.plot_role === 'founder') && Object.keys(plot?.joint_account_contributions || {}).length > 0 && (
              <Section title="Member Contributions" subtitle="Cash each member has pooled into the faction treasury.">
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {Object.entries(plot?.joint_account_contributions || {}).map(([playerId, amount]) => {
                    const member = playerById[Number(playerId)] || null;
                    return (
                      <div key={playerId} className="rounded-3xl border border-slate-800 bg-slate-900/70 p-4">
                        <p className="font-semibold text-white">{member?.username || `Player ${playerId}`}</p>
                        <p className="mt-2 text-xl font-bold text-amber-300">{formatExactMoney(amount)}</p>
                        <p className="mt-1 text-xs text-slate-500">pooled into faction treasury</p>
                      </div>
                    );
                  })}
                </div>
              </Section>
            )}

            <div className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
              <Section title="Current Position" subtitle="See your role, hardship, and command access in the plot.">
                <div className="grid gap-4 lg:grid-cols-2">
                  <div className="rounded-3xl border border-slate-800 bg-slate-900/70 p-4">
                    <p className="text-lg font-semibold text-white">{me?.username || 'Player'}</p>
                    <p className="mt-1 text-xs uppercase tracking-[0.18em] text-slate-500">{me?.plot_role ? me.plot_role.replaceAll('_', ' ') : 'No active plot role'}</p>
                    <div className="mt-4 grid gap-3 sm:grid-cols-3">
                      <div>
                        <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Hardship</p>
                        <p className="mt-1 text-xl font-semibold text-white">{me?.plot_hardship_score || 0}</p>
                      </div>
                      <div>
                        <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Triggers</p>
                        <p className="mt-1 text-xl font-semibold text-white">{me?.plot_hardship_trigger_count || 0}</p>
                      </div>
                      <div>
                        <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Role</p>
                        <div className="mt-1 text-sm font-semibold capitalize text-white">
                          <RoleBadge role={commandEntry?.role || me?.plot_role || 'none'} />
                        </div>
                          <p className="mt-2 text-xs leading-5 text-slate-400">{getRoleSummary(commandEntry || { role: me?.plot_role }).current}</p>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-3xl border border-slate-800 bg-slate-900/70 p-4">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Command Status</p>
                    <p className="mt-2 text-lg font-semibold text-white">{plot?.commander?.username || 'No commander'}</p>
                    <div className="mt-3 space-y-2 text-sm text-slate-300">
                      <p>{isCommander ? 'You currently control admissions and command decisions.' : canIssueOrders ? 'You can issue operations but not membership decisions.' : 'You currently have no command authority.'}</p>
                      <p>{plot?.victory_countdown?.blocked_reason || 'No special countdown block is active right now.'}</p>
                    </div>
                  </div>
                </div>
              </Section>

              <Section title="Strategic Snapshot" subtitle="See the plot's territory, join pressure, and win status.">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-3xl border border-slate-800 bg-slate-900/70 p-4">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Territory</p>
                    <p className="mt-2 text-2xl font-semibold text-white">{plot?.seized_property_ids?.length || 0}</p>
                    <p className="mt-1 text-xs text-slate-400">Seized properties across {plot?.clusters?.length || 0} clusters</p>
                  </div>
                  <div className="rounded-3xl border border-slate-800 bg-slate-900/70 p-4">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Countdown</p>
                    <p className="mt-2 text-2xl font-semibold text-white">
                      {plot?.victory_countdown?.active
                        ? `${plot.victory_countdown.rounds_held}/${plot.victory_countdown.required_rounds}`
                        : plot?.victory_countdown?.countdown_eligible
                        ? 'Ready'
                        : 'Blocked'}
                    </p>
                    <p className="mt-1 text-xs text-slate-400">Victory countdown state</p>
                  </div>
                  <div className="rounded-3xl border border-slate-800 bg-slate-900/70 p-4">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Join Requests</p>
                    <p className="mt-2 text-2xl font-semibold text-white">{pendingJoinRequests.length}</p>
                    <p className="mt-1 text-xs text-slate-400">Pending admissions awaiting command</p>
                  </div>
                  <div className="rounded-3xl border border-slate-800 bg-slate-900/70 p-4">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Coalition</p>
                    <p className="mt-2 text-2xl font-semibold text-white">{plot?.coalition_member_ids?.length || 0}</p>
                    <p className="mt-1 text-xs text-slate-400">Anti-revolution members ready to act</p>
                  </div>
                </div>
              </Section>
            </div>
          </div>
        ) : null}

        {activeTab === 'organization' ? (
          <div className="space-y-5">
            <Section title="Membership Controls" subtitle="Start, join, support, or leave the plot from here.">
              <div className="flex flex-wrap gap-3">
                {!plot?.exists && me?.plot_can_found ? (
                  <button type="button" disabled={isSubmitting} onClick={() => runAction(onPlotStart, {})} className="btn-danger btn-sm">Found The Plot</button>
                ) : null}
                {invitePending ? (
                  <>
                    <button type="button" disabled={isSubmitting} onClick={() => runAction(onPlotJoin, { intent: 'accept' })} className="btn-danger btn-sm">Accept Invitation</button>
                    <button type="button" disabled={isSubmitting} onClick={() => runAction(onPlotJoin, { intent: 'decline' })} className="btn-ghost btn-sm">Decline Invitation</button>
                  </>
                ) : null}
                {!plotMember && !coalitionMember && plot?.exists && !invitePending && me?.plot_hardship_trigger_count >= 0 ? (
                  joinRequestPending ? (
                    <button type="button" disabled={isSubmitting} onClick={() => runAction(onPlotJoin, { intent: 'withdraw_request' })} className="btn-ghost btn-sm">Withdraw Join Request</button>
                  ) : (
                    <button type="button" disabled={isSubmitting} onClick={() => runAction(onPlotJoin, { intent: 'request' })} className="btn-danger btn-sm">Request To Join</button>
                  )
                ) : null}
                {plotMember ? (
                  <button type="button" disabled={isSubmitting} onClick={() => runAction(onPlotJoin, { intent: 'contribute' })} className="btn-ghost btn-sm">Make Contribution</button>
                ) : null}
                {plotMember && !committedMember ? (
                  <button type="button" disabled={isSubmitting} onClick={() => runAction(onPlotJoin, { intent: 'commit' })} className="btn-ghost btn-sm">Commit To The Faction</button>
                ) : null}
                {plotMember ? (
                  <button type="button" disabled={isSubmitting} onClick={() => runAction(onPlotLeave, {})} className="btn-ghost btn-sm">Leave Plot</button>
                ) : null}
              </div>
            </Section>

            <Section title="Chain Of Command" subtitle="See who can lead the plot and who is next in line.">
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {(plot?.command_chain || []).length === 0 ? (
                  <p className="text-sm text-slate-400">No active command structure is available yet.</p>
                ) : (
                  (plot?.command_chain || []).map((entry) => (
                    <div key={entry.player_id} className="rounded-3xl border border-slate-800 bg-slate-900/70 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-white">{entry.username}</p>
                          <div className="mt-1 text-xs uppercase tracking-[0.16em] text-slate-500">
                            <RoleBadge role={entry.role} />
                          </div>
                          <p className="mt-2 text-xs leading-5 text-slate-400">{getRoleSummary(entry).current}</p>
                          <p className="mt-1 text-xs leading-5 text-slate-500">{getRoleSummary(entry).next}</p>
                          {getPromotionProgressLabel(entry) ? <p className="mt-1 text-xs leading-5 text-slate-500">{getPromotionProgressLabel(entry)}</p> : null}
                        </div>
                        <span className={[
                          'rounded-full border px-2 py-1 text-[11px] font-bold uppercase tracking-[0.16em]',
                          entry.is_commander ? 'border-rose-300/60 bg-rose-200 text-slate-950' : 'border-slate-700 text-slate-200',
                        ].join(' ')}>
                          {entry.is_commander ? 'Commander' : entry.is_founder ? 'Founder' : 'Member'}
                        </span>
                      </div>
                      <div className="mt-3 grid gap-3 sm:grid-cols-2 text-sm text-slate-300">
                        <div>
                          <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Joined</p>
                          <p className="mt-1">Round {entry.joined_round || 'n/a'}</p>
                        </div>
                        <div>
                          <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Contribution</p>
                          <p className="mt-1">{entry.contribution_score}</p>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </Section>

            <Section title="Join Requests" subtitle="Review players who are asking to join the plot.">
              <div className="grid gap-3 xl:grid-cols-2">
                {pendingJoinRequests.length === 0 ? (
                  <p className="text-sm text-slate-400">No one is currently asking to join the plot.</p>
                ) : (
                  pendingJoinRequests.map((entry) => (
                    <div key={entry.player_id} className="rounded-3xl border border-slate-800 bg-slate-900/70 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-white">{entry.username}</p>
                          <p className="mt-1 text-xs uppercase tracking-[0.16em] text-slate-500">Requested round {entry.requested_round}</p>
                        </div>
                        <span className="rounded-full border border-slate-700 px-2 py-1 text-[11px] font-bold uppercase tracking-[0.16em] text-slate-200">
                          H {entry.hardship_score}
                        </span>
                      </div>
                      {isCommander ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          <button type="button" disabled={isSubmitting} onClick={() => runAction(onPlotJoin, { intent: 'accept_request', target_player_id: entry.player_id })} className="btn-danger btn-sm">Accept</button>
                          <button type="button" disabled={isSubmitting} onClick={() => runAction(onPlotJoin, { intent: 'decline_request', target_player_id: entry.player_id })} className="btn-ghost btn-sm">Decline</button>
                        </div>
                      ) : (
                        <p className="mt-3 text-xs text-slate-400">Only the current commander can accept or decline requests.</p>
                      )}
                    </div>
                  ))
                )}
              </div>
            </Section>

            <Section title="Recruitment Board" subtitle="Invite eligible players to join the plot.">
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {recruitablePlayers.map((entry) => (
                  <div key={entry.player_id} className="rounded-3xl border border-slate-800 bg-slate-900/70 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-white">{entry.username}</p>
                        <p className="mt-1 text-xs uppercase tracking-[0.16em] text-slate-500">
                          {entry.requested_to_join ? 'Requested entry' : entry.invited ? 'Already invited' : 'Recruitable'}
                        </p>
                      </div>
                      <span className="rounded-full border border-slate-700 px-2 py-1 text-[11px] font-bold uppercase tracking-[0.16em] text-slate-200">
                        H {entry.hardship_score}
                      </span>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {(entry.hardship_reasons || []).slice(0, 2).map((reason) => (
                        <span key={`${entry.player_id}-${reason}`} className="rounded-full border border-slate-700 px-2 py-1 text-[11px] text-slate-300">{reason}</span>
                      ))}
                    </div>
                    {isCommander && organizationAction && !entry.invited && !entry.requested_to_join ? (
                      <button
                        type="button"
                        disabled={isSubmitting}
                        onClick={() => runAction(onPlotAction, { action_type: organizationAction, target_player_id: entry.player_id })}
                        className="btn-danger btn-sm mt-3"
                      >
                        {organizationAction === 'recruit_publicly' ? 'Invite Publicly' : 'Invite Quietly'}
                      </button>
                    ) : null}
                  </div>
                ))}
              </div>
            </Section>
          </div>
        ) : null}

        {activeTab === 'territories' ? (
          <div className="space-y-5">
            <Section title="Seized Properties" subtitle="See which properties the plot controls and how secure they are.">
              {(plot?.seized_properties || []).length === 0 ? (
                <p className="text-sm text-slate-400">No territory is under revolutionary control yet.</p>
              ) : (
                <div className="grid gap-4 xl:grid-cols-2">
                  {(plot?.seized_properties || []).map((entry) => (
                    <div key={entry.property_id} className="rounded-3xl border border-rose-500/20 bg-rose-500/10 p-5 text-sm text-rose-50">
                      <div className="flex flex-wrap items-start justify-between gap-4">
                        <div>
                          <p className="text-xl font-semibold text-white">{entry.property_name}</p>
                          <p className="mt-1 text-xs uppercase tracking-[0.18em] text-rose-100/80">{entry.region} • Space {entry.board_position}</p>
                        </div>
                        <span className="rounded-full border border-rose-400/30 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.16em] text-rose-100">
                          {entry.cluster_id || 'solo'}
                        </span>
                      </div>
                      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                        <div>
                          <p className="text-[11px] uppercase tracking-[0.18em] text-rose-100/70">Entrenchment</p>
                          <p className="mt-1 text-xl font-semibold text-white">{entry.entrenchment}</p>
                        </div>
                        <div>
                          <p className="text-[11px] uppercase tracking-[0.18em] text-rose-100/70">Supply Yield</p>
                          <p className="mt-1 text-xl font-semibold text-white">{entry.supply_yield}</p>
                        </div>
                        <div>
                          <p className="text-[11px] uppercase tracking-[0.18em] text-rose-100/70">Reintegration</p>
                          <p className="mt-1 text-xl font-semibold text-white">{entry.reintegration_progress}%</p>
                        </div>
                        <div>
                          <p className="text-[11px] uppercase tracking-[0.18em] text-rose-100/70">Board Value</p>
                          <p className="mt-1 text-xl font-semibold text-white">{formatMoney(entry.current_value)}</p>
                        </div>
                      </div>
                      <p className="mt-4 text-xs text-rose-100/80">{entry.blockaded ? 'Currently blockaded.' : 'No active blockade on this property.'}</p>
                    </div>
                  ))}
                </div>
              )}
            </Section>

            <div className="grid gap-5 xl:grid-cols-2">
              <Section title="Clusters" subtitle="Grouped seized properties with shared entrenchment and reintegration risk.">
                <div className="space-y-3">
                  {(plot?.clusters || []).length === 0 ? (
                    <p className="text-sm text-slate-400">No live seized clusters yet.</p>
                  ) : (
                    (plot?.clusters || []).map((cluster) => (
                      <div key={cluster.cluster_id} className="rounded-3xl border border-slate-800 bg-slate-900/70 p-4 text-sm text-slate-200">
                        <div className="flex items-center justify-between gap-3">
                          <p className="font-semibold text-white">{cluster.cluster_id}</p>
                          <span className="rounded-full border border-slate-700 px-2 py-1 text-[11px] font-bold uppercase tracking-[0.16em] text-slate-200">
                            {cluster.entrenched ? 'Entrenched' : 'Loose'}
                          </span>
                        </div>
                        <p className="mt-2 text-xs text-slate-400">{cluster.region_names.join(' • ') || 'No region data'} • {cluster.size} tiles</p>
                        <p className="mt-2 text-xs text-slate-400">Average entrenchment {cluster.avg_entrenchment} • Reintegration pressure {cluster.reintegration_pressure}%</p>
                      </div>
                    ))
                  )}
                </div>
              </Section>

              <Section title="Legal Seizure Targets" subtitle="These properties can be agitated, sabotaged, or seized.">
                <div className="space-y-3">
                  {(plot?.legal_targets || []).length === 0 ? (
                    <p className="text-sm text-slate-400">No legal seizure targets are currently exposed.</p>
                  ) : (
                    (plot?.legal_targets || []).map((entry) => (
                      <div key={entry.property_id} className="rounded-3xl border border-slate-800 bg-slate-900/70 p-4 text-sm text-slate-200">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="font-semibold text-white">{entry.property_name}</p>
                            <p className="mt-1 text-xs uppercase tracking-[0.16em] text-slate-500">{entry.region} • owned by {entry.owner_name}</p>
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
              </Section>
            </div>
          </div>
        ) : null}

        {activeTab === 'operations' ? (
          <div className="space-y-5">
            <Section title="Global Operations" subtitle="Use region-wide actions that are not tied to one property.">
              {!plotMember ? (
                <p className="text-sm text-slate-400">Only active plot members can issue revolutionary operations.</p>
              ) : !canIssueOrders ? (
                <p className="text-sm text-slate-400">Your current rank does not have operational authority.</p>
              ) : globalOperations.length === 0 ? (
                <p className="text-sm text-slate-400">No global or regional operations are currently unlocked.</p>
              ) : (
                <div className="grid gap-4 xl:grid-cols-2">
                  {globalOperations.map((definition) => (
                    <ActionCard
                      key={definition.action_type}
                      definition={definition}
                      selection={operationSelections[definition.action_type] || {}}
                      onSelectionChange={(patch) => updateOperationSelection(definition.action_type, patch)}
                      onRun={() => runAction(onPlotAction, buildPayload(definition, operationSelections[definition.action_type] || {}))}
                      disabled={isSubmitting}
                      regionOptions={regionOptions}
                      clusters={plot?.clusters || []}
                    />
                  ))}
                </div>
              )}
            </Section>

            {isCommander && organizerPromotionAction ? (
              <Section title="Promotions" subtitle="Promote eligible members so they can issue plot operations.">
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {(plot?.command_chain || []).filter((entry) => entry.role === 'sympathizer').map((entry) => (
                    <div key={entry.player_id} className="rounded-3xl border border-slate-800 bg-slate-900/70 p-4">
                      <p className="font-semibold text-white">{entry.username}</p>
                      <div className="mt-1 flex flex-wrap items-center gap-1 text-xs uppercase tracking-[0.16em] text-slate-500">
                        <RoleBadge role={entry.role} /> to <RoleBadge role={entry.next_role} />
                      </div>
                      <p className="mt-2 text-xs leading-5 text-slate-400">{getRoleSummary(entry).current}</p>
                      <p className="mt-1 text-xs leading-5 text-slate-500">{getRoleSummary(entry).next}</p>
                      <p className={[
                        'mt-2 text-xs leading-5',
                        entry.promotion_ready ? 'text-emerald-200' : 'text-amber-200',
                      ].join(' ')}>
                        {entry.promotion_ready
                          ? `Ready to promote. Contribution rounds: ${entry.contribution_round_count}/${entry.required_contribution_rounds}.`
                          : `Needs ${entry.required_contribution_rounds} contribution rounds. Current progress: ${entry.contribution_round_count}/${entry.required_contribution_rounds}.`}
                      </p>
                      <button
                        type="button"
                        disabled={isSubmitting || !entry.promotion_ready}
                        onClick={() => runAction(onPlotAction, { action_type: organizerPromotionAction.action_type, target_player_id: entry.player_id })}
                        className="btn-ghost btn-sm mt-3"
                      >
                        Promote
                      </button>
                    </div>
                  ))}
                </div>
              </Section>
            ) : null}
          </div>
        ) : null}

        {activeTab === 'counterplay' ? (
          <div className="space-y-5">
            <Section title="Coalition Access" subtitle="Join the coalition to unlock actions against the plot.">
              <div className="flex flex-wrap gap-3 text-sm text-slate-200">
                <div className="rounded-3xl border border-slate-800 bg-slate-900/70 px-4 py-3">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Coalition Unlocked</p>
                  <p className="mt-1 text-lg font-semibold text-white">{plot?.coalition_unlocked ? 'Yes' : 'No'}</p>
                </div>
                <div className="rounded-3xl border border-slate-800 bg-slate-900/70 px-4 py-3">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Coalition Members</p>
                  <p className="mt-1 text-lg font-semibold text-white">{plot?.coalition_member_ids?.length || 0}</p>
                </div>
              </div>
              {plot?.public && !plotMember && !coalitionMember && plot?.coalition_unlocked ? (
                <button
                  type="button"
                  disabled={isSubmitting}
                  onClick={() => runAction(onPlotCounterAction, { action_type: 'join_coalition' })}
                  className="btn-primary btn-sm mt-4"
                >
                  Join Anti-Revolution Coalition
                </button>
              ) : null}
            </Section>

            <Section title="Global Counterplay" subtitle="Use region-wide actions to slow the plot and lower unrest.">
              {!plot?.public ? (
                <p className="text-sm text-slate-400">Public counterplay unlocks only after the plot becomes public.</p>
              ) : !coalitionMember ? (
                <p className="text-sm text-slate-400">Join the coalition to access global counter-actions.</p>
              ) : (
                <div className="space-y-4">
                  {coalitionSupporters.length > 0 ? (
                    <div className="rounded-3xl border border-cyan-900/40 bg-cyan-950/10 p-4">
                      <label className="flex items-center gap-3 text-sm text-cyan-100">
                        <input
                          type="checkbox"
                          checked={shareCounterFunding}
                          onChange={(event) => setShareCounterFunding(event.target.checked)}
                          className="h-4 w-4 rounded border-slate-600 bg-slate-950 text-cyan-400"
                        />
                        Pool coalition cash with selected supporters
                      </label>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {coalitionSupporters.map((player) => {
                          const checked = selectedSupporterIds.includes(player.id);
                          return (
                            <label key={player.id} className="inline-flex items-center gap-2 rounded-full border border-cyan-900/40 px-3 py-2 text-xs text-cyan-50">
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={(event) => {
                                  setSelectedSupporterIds((current) => (
                                    event.target.checked
                                      ? [...current, player.id]
                                      : current.filter((value) => value !== player.id)
                                  ));
                                }}
                                className="h-3.5 w-3.5 rounded border-slate-600 bg-slate-950 text-cyan-400"
                              />
                              {player.username}
                            </label>
                          );
                        })}
                      </div>
                    </div>
                  ) : null}

                  <div className="grid gap-4 xl:grid-cols-2">
                    {globalCounterActions.map((definition) => (
                      <ActionCard
                        key={definition.action_type}
                        definition={definition}
                        selection={counterSelections[definition.action_type] || {}}
                        onSelectionChange={(patch) => updateCounterSelection(definition.action_type, patch)}
                        onRun={() => runAction(onPlotCounterAction, buildCounterPayload(definition, counterSelections[definition.action_type] || {}))}
                        disabled={isSubmitting}
                        regionOptions={regionOptions}
                        clusters={plot?.clusters || []}
                        buttonTone="btn-primary"
                      />
                    ))}
                  </div>
                </div>
              )}
            </Section>
          </div>
        ) : null}
      </div>
    </div>
  );
}