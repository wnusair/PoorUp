import { useEffect, useMemo, useState } from 'react';
import HelpTooltip from '../Common/HelpTooltip';
import { useGameStore } from '../../hooks/useGameState';
import { formatExactMoney, formatMoney } from '../../utils/formatters';
import { getGrievanceLabel, getIncidentLabel } from '../../utils/socialCopy';
import {
  calculateDevelopmentCost,
  calculateDevelopmentRefund,
  calculatePropertyRent,
  getDevelopmentLabel,
  getPropertyRentSchedule,
  isMinarchismEconomy,
} from '../../utils/propertyEconomy';
import {
  canSellPropertyDevelopment,
  canDevelopProperty,
  getDevelopmentBlockReason,
  getPropertyDevelopmentLevel,
  getPropertySet,
  getSellDevelopmentBlockReason,
  hasMonopoly,
} from '../../utils/propertyRules';
import { normalizeGovernmentType } from '../../utils/gameState';


function getOwnerName(ownerId, players) {
  if (!ownerId) return 'Unowned';
  return players.find((player) => player.id === ownerId)?.username || 'Unknown owner';
}


function resolveLiveProperty(sourceProperty, actionData, properties) {
  const positionCandidates = [
    sourceProperty?.board_position,
    sourceProperty?.position,
    actionData?.position,
  ].filter((value) => value != null);

  for (const position of positionCandidates) {
    if (properties[position]) {
      return { ...sourceProperty, ...properties[position] };
    }
  }

  const propertyIdCandidates = [sourceProperty?.id, actionData?.property_id].filter((value) => value != null);
  for (const propertyId of propertyIdCandidates) {
    const liveProperty = Object.values(properties || {}).find((entry) => entry.id === propertyId);
    if (liveProperty) {
      return { ...sourceProperty, ...liveProperty };
    }
  }

  return sourceProperty || null;
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


function formatPlotCost(definition) {
  if (!definition) {
    return 'No action data';
  }
  if (definition.cash_cost != null && definition.cash_cost > 0) {
    return `${formatExactMoney(definition.cash_cost)}${definition.supporters_required ? ` + ${definition.supporters_required} supporter${definition.supporters_required === 1 ? '' : 's'}` : ''}`;
  }
  const entries = Object.entries(definition.cost || {});
  if (!entries.length) {
    return 'No direct cost';
  }
  return entries.map(([key, value]) => `${value} ${key}`).join(' + ');
}


const PLOT_ACTION_UI = {
  attempt_seizure: {
    title: 'Seize Property',
    summary: 'Launch the actual takeover now that this property is exposed.',
  },
  agitate_property: {
    title: 'Increase Support',
    summary: 'Raise local agitation so a later seizure is more realistic.',
  },
  sabotage_development: {
    title: 'Disrupt Owner',
    summary: 'Make this property less stable and harder for its owner to exploit.',
  },
  fortify_property: {
    title: 'Harden Territory',
    summary: 'Make this seized property harder to claw back.',
  },
  defend_reintegration: {
    title: 'Block Reintegration',
    summary: 'Spend supply to slow the current reintegration push.',
  },
  labor_settlement: {
    title: 'Reduce Agitation',
    summary: 'Take heat out of this property before it becomes a better target.',
  },
  security_subsidy: {
    title: 'Make Seizure Harder',
    summary: 'Harden this property against future seizure attempts.',
  },
  reintegration_campaign: {
    title: 'Reintegrate Property',
    summary: 'Push this seized property back into normal control.',
  },
};


export default function PropertyModal({
  data = null,
  property: propertyProp = null,
  mode = 'prompt',
  onBuy,
  onDecline,
  onDevelop,
  onMortgage,
  onSellHouse,
  onUnmortgage,
  onPlotAction,
  onPlotCounterAction,
  onOpenPlotPanel,
  onClose,
}) {
  const {
    pendingAction,
    myPlayerId,
    currentPlayerId,
    players,
    properties,
    economy,
    social,
  } = useGameStore();
  const [timeLeft, setTimeLeft] = useState(30);
  const [activeTab, setActiveTab] = useState('property');
  const [plotStatus, setPlotStatus] = useState('');
  const [plotSubmitting, setPlotSubmitting] = useState(false);
  const [shareCounterFunding, setShareCounterFunding] = useState(false);
  const [selectedCoalitionSupporters, setSelectedCoalitionSupporters] = useState([]);

  const actionData = data || pendingAction?.data || null;
  const property = resolveLiveProperty(propertyProp || actionData?.property, actionData, properties);

  useEffect(() => {
    setTimeLeft(30);
  }, [actionData?.property_id, property?.id, mode]);

  useEffect(() => {
    setActiveTab('property');
    setPlotStatus('');
    setPlotSubmitting(false);
    setShareCounterFunding(false);
    setSelectedCoalitionSupporters([]);
  }, [property?.id]);

  const me = players.find((player) => player.id === myPlayerId) || null;
  const owner = property?.owner_id ? players.find((player) => player.id === property.owner_id) : null;
  const corporations = economy?.corporations?.by_id || economy?.corporations?.entities || {};
  const corporateOwner = property?.corporate_owner_id ? corporations[String(property.corporate_owner_id)] : null;
  const isMyTurn = currentPlayerId === myPlayerId;
  const isOwnedByMe = property?.owner_id === myPlayerId;
  const socialRestrictionReason = property.social_unionized
    ? 'This property is controlled by the Proletariat Union and cannot be privately managed.'
    : null;
  const isPromptForMe = actionData?.player_id === myPlayerId
    && property
    && (actionData?.property_id === property.id || actionData?.position === property.board_position);
  const isCorporatePrompt = (pendingAction?.type || actionData?.type) === 'buy_corporate_property';
  const corporateBuyoutPrice = Number(property?.corporate_listing_price || property?.current_value || property?.base_price || 0);
  const canSubmitCorporateBuyout = Boolean(
    isCorporatePrompt
    && corporateOwner
    && property?.corporate_owner_id
    && !property?.owner_id
    && Number(me?.balance || 0) >= corporateBuyoutPrice,
  );

  useEffect(() => {
    if (!isPromptForMe) return undefined;
    if (timeLeft <= 0) {
      onDecline?.();
      return undefined;
    }

    const timer = setTimeout(() => setTimeLeft((value) => value - 1), 1000);
    return () => clearTimeout(timer);
  }, [timeLeft, isPromptForMe, onDecline]);

  if (!property) return null;

  const plot = social?.plot || {};
  const socialProperty = social?.properties?.[String(property.id)] || {};
  const commandEntry = (plot?.command_chain || []).find((entry) => entry.player_id === myPlayerId) || null;
  const plotMember = Boolean(plot?.member_ids?.includes(myPlayerId));
  const coalitionMember = Boolean(plot?.coalition_member_ids?.includes(myPlayerId));
  const canIssuePlotOrders = Boolean(commandEntry?.can_issue_orders || (plotMember && (me?.plot_role || '') !== 'sympathizer'));
  const propertyIsSeized = Boolean(plot?.seized_property_ids?.includes(property.id) || socialProperty?.plot_seized || property.owner_id === 'communist_plot');
  const legalTarget = (plot?.legal_targets || []).find((entry) => entry.property_id === property.id) || null;
  const seizedEntry = (plot?.seized_properties || []).find((entry) => entry.property_id === property.id) || null;
  const coalitionSupporters = useMemo(
    () => (plot?.coalition_member_ids || []).map((playerId) => players.find((player) => player.id === playerId)).filter((player) => player && player.id !== myPlayerId),
    [myPlayerId, players, plot?.coalition_member_ids],
  );

  const revolutionaryActions = useMemo(() => {
    const definitions = Object.fromEntries((plot?.action_catalog || []).map((entry) => [entry.action_type, entry]));
    const actions = [];

    if (plotMember && canIssuePlotOrders && legalTarget && definitions.attempt_seizure && definitions.attempt_seizure.stage <= (plot?.stage || 0)) {
      actions.push({ ...definitions.attempt_seizure, action_type: 'attempt_seizure' });
    }
    if (plotMember && canIssuePlotOrders && !propertyIsSeized && definitions.agitate_property && definitions.agitate_property.stage <= (plot?.stage || 0)) {
      actions.push({ ...definitions.agitate_property, action_type: 'agitate_property' });
    }
    if (plotMember && canIssuePlotOrders && !propertyIsSeized && definitions.sabotage_development && definitions.sabotage_development.stage <= (plot?.stage || 0)) {
      actions.push({ ...definitions.sabotage_development, action_type: 'sabotage_development' });
    }
    if (plotMember && canIssuePlotOrders && seizedEntry && definitions.fortify_property && definitions.fortify_property.stage <= (plot?.stage || 0)) {
      actions.push({ ...definitions.fortify_property, action_type: 'fortify_property' });
    }
    if (plotMember && canIssuePlotOrders && seizedEntry && Number(seizedEntry.reintegration_progress || 0) > 0 && definitions.defend_reintegration && definitions.defend_reintegration.stage <= (plot?.stage || 0)) {
      actions.push({ ...definitions.defend_reintegration, action_type: 'defend_reintegration' });
    }

    return actions;
  }, [canIssuePlotOrders, legalTarget, plot?.action_catalog, plot?.stage, plotMember, propertyIsSeized, seizedEntry]);

  const counterplayActions = useMemo(() => {
    const definitions = Object.fromEntries((plot?.counter_action_catalog || []).map((entry) => [entry.action_type, entry]));
    const actions = [];

    if (coalitionMember && plot?.public && !propertyIsSeized && definitions.labor_settlement) {
      actions.push({ ...definitions.labor_settlement, action_type: 'labor_settlement' });
    }
    if (coalitionMember && plot?.public && !propertyIsSeized && definitions.security_subsidy) {
      actions.push({ ...definitions.security_subsidy, action_type: 'security_subsidy' });
    }
    if (coalitionMember && plot?.public && seizedEntry && definitions.reintegration_campaign) {
      actions.push({ ...definitions.reintegration_campaign, action_type: 'reintegration_campaign' });
    }

    return actions;
  }, [coalitionMember, plot?.counter_action_catalog, plot?.public, propertyIsSeized, seizedEntry]);

  const hasPlotTab = !isPromptForMe && property.property_type !== 'special' && (
    plot?.exists
    || plot?.public
    || propertyIsSeized
    || Boolean(legalTarget)
    || coalitionMember
    || plotMember
  );

  async function runPlotLocalAction(handler, payload) {
    if (!handler) {
      return;
    }
    setPlotSubmitting(true);
    setPlotStatus('');
    try {
      const result = await handler(payload);
      setPlotStatus(result?.summary || 'Action resolved.');
    } catch (error) {
      setPlotStatus(error?.message || 'Action failed.');
    } finally {
      setPlotSubmitting(false);
    }
  }

  function buildCounterPayload(definition) {
    const payload = {
      action_type: definition.action_type,
      property_id: property.id,
    };
    if ((definition.cash_cost || 0) > 0) {
      payload.contributors = shareCounterFunding
        ? equalSplitContributors(myPlayerId, selectedCoalitionSupporters, definition.cash_cost)
        : [{ player_id: myPlayerId, amount: definition.cash_cost }];
    }
    if ((definition.supporters_required || 0) > 0) {
      payload.supporter_ids = [myPlayerId, ...selectedCoalitionSupporters];
    }
    return payload;
  }

  const groupColor = property.group_color || property.groupColor;
  const developmentLevel = getPropertyDevelopmentLevel(property);
  const developmentCost = calculateDevelopmentCost(property.base_price, developmentLevel + 1, economy);
  const sellRefund = calculateDevelopmentRefund(property.base_price, developmentLevel, economy);
  const mortgageValue = Number(property.base_price || 0) * 0.5;
  const unmortgageCost = mortgageValue * 1.1;
  const currentRent = calculatePropertyRent(property, properties, economy);
  const rentSchedule = getPropertyRentSchedule(property, properties, economy);
  const uncappedDevelopment = isMinarchismEconomy(economy);
  const dealModifiers = Array.isArray(property.deal_modifiers) ? property.deal_modifiers : [];
  const dealInvestmentOptions = Array.isArray(property.deal_investment_options) ? property.deal_investment_options : [];
  const dealProfitObligations = Array.isArray(property.deal_profit_obligations) ? property.deal_profit_obligations : [];
  const ownsMonopoly = hasMonopoly(property, properties);
  const setProperties = getPropertySet(property, properties);
  const controlledSetCount = setProperties.filter((entry) => entry.owner_id === myPlayerId).length;
  const ownsFullSet = setProperties.length > 0 && setProperties.every((entry) => entry.owner_id === myPlayerId);
  const turnLockReason = !isMyTurn ? 'Property management is only available on your turn.' : null;
  const baseDevelopReason = getDevelopmentBlockReason(property, properties, myPlayerId, economy);
  const standardDevelopReason = socialRestrictionReason || turnLockReason || baseDevelopReason || ((me?.balance || 0) < developmentCost
    ? `You need ${formatMoney(developmentCost)} to build here.`
    : null);
  const escrowBuildOptions = dealInvestmentOptions.filter((option) => Number(option.escrow_remaining || 0) >= developmentCost);
  const canDevelop = isMyTurn && !isPromptForMe && !standardDevelopReason && canDevelopProperty(property, properties, myPlayerId, economy);
  const canDevelopWithEscrow = isMyTurn && !isPromptForMe && !socialRestrictionReason && !turnLockReason && !baseDevelopReason && escrowBuildOptions.length > 0;
  const developReason = standardDevelopReason || (canDevelopWithEscrow
    ? `Cash is short, but investor escrow can cover ${formatMoney(developmentCost)}.`
    : null);
  const sellReason = socialRestrictionReason || turnLockReason || getSellDevelopmentBlockReason(property, properties, myPlayerId);
  const canSellHouse = isMyTurn
    && !isPromptForMe
    && !sellReason
    && canSellPropertyDevelopment(property, properties, myPlayerId);
  const mortgageReason = socialRestrictionReason || turnLockReason || (!isOwnedByMe
    ? 'You must own this property to mortgage it.'
    : property.is_mortgaged
      ? 'This property is already mortgaged.'
      : developmentLevel > 0
        ? 'Sell the houses on this property before mortgaging it.'
        : null);
  const canMortgage = isMyTurn && !isPromptForMe && isOwnedByMe && !property.is_mortgaged && developmentLevel === 0;
  const unmortgageReason = socialRestrictionReason || turnLockReason || (!isOwnedByMe
    ? 'You must own this property to unmortgage it.'
    : !property.is_mortgaged
      ? 'This property is not mortgaged.'
      : (me?.balance || 0) < unmortgageCost
        ? `You need ${formatMoney(unmortgageCost)} to unmortgage it.`
        : null);
  const canUnmortgage = isMyTurn && !isPromptForMe && isOwnedByMe && property.is_mortgaged && !unmortgageReason;
  const title = isPromptForMe ? 'Property Decision' : 'Property Details';
  const statusText = property.social_unionized
    ? 'Controlled by the Proletariat Union'
    : corporateOwner
    ? `Listed by ${corporateOwner.name || corporateOwner.stock_symbol || 'a corporation'}`
    : property.is_mortgaged
    ? 'Mortgaged'
    : owner
      ? `Owned by ${owner.username}`
      : 'Unowned';
  const governmentType = normalizeGovernmentType(economy?.gov_type || economy?.government_type || 'liberal_democracy');
  const isLiberalDemocracy = governmentType === 'liberal_democracy';

  return (
    <div className="modal-overlay">
      <div className="modal-panel modal-panel--wide max-w-5xl max-h-[88vh] overflow-y-auto">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="min-w-0 flex-1">
            <p className="text-xs uppercase tracking-widest text-gray-500 mb-2">{title}</p>
            <div
              className="w-full h-2 rounded-full mb-4"
              style={{ backgroundColor: groupColor || '#4B5563' }}
            />
            <h2 className="text-2xl font-bold text-white leading-tight">{property.name}</h2>
            <p className="text-sm text-gray-400 mt-1">
              {property.region || 'Special'} · Space {property.board_position}
            </p>
          </div>
          <button onClick={onClose} className="btn-ghost btn-sm">
            Close
          </button>
        </div>

        <div className="grid grid-cols-2 gap-3 mb-6 lg:grid-cols-4">
          <div className="econ-stat">
            <span className="econ-stat__label">Price</span>
            <span className="econ-stat__value text-blue-300">
              {formatMoney(property.current_value || property.base_price)}
            </span>
          </div>
          <div className="econ-stat">
            <span className="econ-stat__label">Current Rent</span>
            <span className="econ-stat__value text-orange-300">{formatExactMoney(currentRent)}</span>
          </div>
          <div className="econ-stat">
            <span className="econ-stat__label">Houses Built</span>
            <span className="econ-stat__value text-gray-200">{getDevelopmentLabel(developmentLevel, economy)}</span>
          </div>
          <div className="econ-stat">
            <span className="econ-stat__label">Mortgage</span>
            <span className="econ-stat__value text-green-300">{formatMoney(mortgageValue)}</span>
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.95fr)]">
          <div className="min-w-0 space-y-6">
            {property.property_type === 'property' && rentSchedule.length > 0 && (
              <div className="rounded-xl border border-gray-700 bg-gray-900/70 p-4 space-y-3">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-xs uppercase tracking-widest text-gray-500">Rent Ladder</p>
                    <p className="text-sm text-gray-300 mt-1">See the rent at each development level directly from the property card.</p>
                  </div>
                  {uncappedDevelopment && (
                    <span className="rounded-full border border-amber-700/60 bg-amber-950/30 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-200">
                      No cap
                    </span>
                  )}
                </div>

                <div className="grid max-h-64 grid-cols-2 gap-2 overflow-y-auto pr-1 sm:grid-cols-3 xl:grid-cols-2 2xl:grid-cols-3">
                  {rentSchedule.map((entry) => {
                    const isCurrentLevel = entry.level === developmentLevel;
                    return (
                      <div
                        key={entry.level}
                        className={[
                          'rounded-lg border px-3 py-2',
                          isCurrentLevel ? 'border-orange-500 bg-orange-500/10 text-orange-100' : 'border-gray-700 bg-gray-800/80 text-gray-100',
                        ].join(' ')}
                      >
                        <p className="text-[11px] uppercase tracking-[0.18em] text-gray-400">{getDevelopmentLabel(entry.level, economy)}</p>
                        <p className="mt-1 text-sm font-semibold">{formatExactMoney(entry.rent)}</p>
                      </div>
                    );
                  })}
                </div>

                {uncappedDevelopment && (
                  <p className="text-xs text-gray-400">
                    Minarchism keeps scaling past four houses. This ladder shows every built level plus the next four upgrades.
                  </p>
                )}
              </div>
            )}

            <div className="rounded-xl border border-gray-700 bg-gray-900/70 p-4 space-y-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs uppercase tracking-widest text-gray-500">Set Overview</p>
                  <p className="text-sm text-gray-300 mt-1">
                    {property.property_type === 'property'
                      ? `Own ${controlledSetCount} of ${setProperties.length} properties in this set.`
                      : `Own ${controlledSetCount} of ${setProperties.length} transit spaces in this network.`}
                  </p>
                </div>
                <span
                  className={[
                    'px-3 py-1 rounded-full text-xs font-semibold border',
                    ownsFullSet ? 'border-green-700 bg-green-950/40 text-green-300' : 'border-gray-700 bg-gray-800 text-gray-300',
                  ].join(' ')}
                >
                  {ownsFullSet ? 'Full set owned' : `${controlledSetCount}/${setProperties.length} owned`}
                </span>
              </div>

              <div className="grid gap-2 lg:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
                {setProperties.map((setProperty) => {
                  const setPropertyLevel = getPropertyDevelopmentLevel(setProperty);
                  const isSelected = (setProperty.id != null && setProperty.id === property.id)
                    || setProperty.board_position === property.board_position;

                  return (
                    <div
                      key={setProperty.id ?? setProperty.board_position}
                      className={[
                        'rounded-lg border p-3 transition-colors',
                        isSelected ? 'border-blue-500 bg-blue-900/20' : 'border-gray-700 bg-gray-800/80',
                      ].join(' ')}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-white truncate">{setProperty.name}</p>
                          <p className="text-xs text-gray-400 mt-1">
                            Owner: <span className="text-gray-200">{getOwnerName(setProperty.owner_id, players)}</span>
                          </p>
                        </div>
                        <div className="text-right flex-shrink-0">
                          <p className="text-xs uppercase tracking-wide text-gray-500">Build</p>
                          <p className="text-sm font-medium text-gray-200">
                            {setProperty.property_type === 'property' ? getDevelopmentLabel(setPropertyLevel, economy) : 'Not developable'}
                          </p>
                        </div>
                      </div>
                      {setProperty.is_mortgaged && (
                        <p className="text-xs text-red-300 mt-2">Mortgaged</p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="min-w-0 space-y-6">
            <div className="rounded-lg border border-gray-700 bg-gray-800 p-4 space-y-2">
              <div className="flex items-center justify-between gap-3 text-sm">
                <span className="text-gray-400">Status</span>
                <span className="text-white font-medium text-right">{statusText}</span>
              </div>
              <div className="flex items-center justify-between gap-3 text-sm">
                <span className="text-gray-400">Type</span>
                <span className="text-white font-medium capitalize">{property.property_type}</span>
              </div>
              <div className="flex items-center justify-between gap-3 text-sm">
                <span className="text-gray-400">Monopoly</span>
                <span className="text-white font-medium">{ownsMonopoly ? 'Yes' : 'No'}</span>
              </div>
              {property.is_mortgaged && (
                <div className="flex items-center justify-between gap-3 text-sm">
                  <span className="text-gray-400">Unmortgage Cost</span>
                  <span className="text-white font-medium">{formatMoney(unmortgageCost)}</span>
                </div>
              )}
              {(property.social_incident_type || property.social_unionized) && (
                <div className="rounded-lg border border-rose-900/60 bg-rose-950/30 p-3 text-sm text-rose-100">
                  <p className="font-semibold uppercase tracking-wide text-rose-200">
                    {property.social_unionized ? 'Taken over by the union' : `${getIncidentLabel(property.social_incident_type)} underway`}
                  </p>
                  <p className="mt-1 text-xs text-rose-100/80">
                    <span className="inline-flex items-center gap-1">
                      <span>Local pressure</span>
                      <HelpTooltip content="How close this property is to its next protest, strike, uprising, or takeover." label="Local pressure help" />
                    </span>
                    {' '}{Math.round(Number(property.social_tension || 0))}
                    {' '}•{' '}
                    <span className="inline-flex items-center gap-1">
                      <span>Area pressure</span>
                      <HelpTooltip content="How likely unrest here is to spread across this owner's nearby properties in the region." label="Area pressure help" />
                    </span>
                    {' '}{Math.round(Number(property.social_territory_instability || 0))}
                  </p>
                  {property.social_dominant_grievance && (
                    <p className="mt-1 text-xs text-rose-100/70">
                      <span className="inline-flex items-center gap-1">
                        <span>Main cause</span>
                        <HelpTooltip content="The biggest reason this property is gaining unrest right now." label="Main cause help" />
                      </span>
                      : {getGrievanceLabel(property.social_dominant_grievance)}
                    </p>
                  )}
                </div>
              )}
              {isLiberalDemocracy && corporateOwner && (
                <div className="rounded-lg border border-cyan-900/60 bg-cyan-950/30 p-3 text-sm text-cyan-100">
                  <p className="font-semibold uppercase tracking-wide text-cyan-200">Corporate Listing</p>
                  <p className="mt-1 text-xs text-cyan-100/80">
                    {corporateOwner.name || corporateOwner.stock_symbol} is holding this property. Buyout price: {formatMoney(property.corporate_listing_price || property.current_value || property.base_price)}.
                  </p>
                  <p className="mt-1 text-xs text-cyan-100/70">
                    Corporate rent if you decline: {formatExactMoney(property.corporate_rent || currentRent)}.
                  </p>
                </div>
              )}
            </div>

            {hasPlotTab && (
              <div className="rounded-xl border border-gray-700 bg-gray-900/70 p-2">
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setActiveTab('property')}
                    className={[
                      'rounded-lg px-3 py-2 text-sm font-semibold transition',
                      activeTab === 'property' ? 'bg-white text-gray-950' : 'text-gray-300 hover:bg-gray-800',
                    ].join(' ')}
                  >
                    Property
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveTab('plot')}
                    className={[
                      'rounded-lg px-3 py-2 text-sm font-semibold transition',
                      activeTab === 'plot' ? 'bg-rose-200 text-gray-950' : 'text-gray-300 hover:bg-gray-800',
                    ].join(' ')}
                  >
                    Plot
                  </button>
                </div>
              </div>
            )}

            {activeTab === 'property' && (dealModifiers.length > 0 || dealInvestmentOptions.length > 0 || dealProfitObligations.length > 0) && (
              <div className="rounded-xl border border-emerald-900/60 bg-emerald-950/20 p-4 space-y-3">
                <div>
                  <p className="text-xs uppercase tracking-widest text-emerald-300">Deal Effects</p>
                  <p className="mt-1 text-sm text-emerald-100/80">This property has an active deal attached to it.</p>
                </div>

                {dealModifiers.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-200">Rent Modifiers</p>
                    {dealModifiers.map((modifier, index) => (
                      <div key={`${modifier.deal_id}-${modifier.type}-${index}`} className="rounded-lg border border-emerald-800/60 bg-gray-900/60 px-3 py-2 text-sm text-emerald-50">
                        <p className="font-medium">{modifier.type === 'rent_immunity' ? 'Rent immunity applies' : `Rent discount: ${Math.round((1 - Number(modifier.rent_multiplier || 1)) * 100)}% off`}</p>
                        <p className="mt-1 text-xs text-emerald-100/70">{modifier.deadline?.remaining ?? modifier.deadline?.initial ?? 0} uses remain for the beneficiary.</p>
                      </div>
                    ))}
                  </div>
                )}

                {dealInvestmentOptions.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-200">
                      <span className="inline-flex items-center gap-1">
                        <span>Build Money Available</span>
                        <HelpTooltip content="This is money from an active build loan that can still be spent on upgrades here." label="Build money help" />
                      </span>
                    </p>
                    {dealInvestmentOptions.map((option) => (
                      <div key={`${option.deal_id}-${option.clause_id}`} className="rounded-lg border border-emerald-800/60 bg-gray-900/60 px-3 py-2 text-sm text-emerald-50">
                        <p>Build money left: {formatMoney(option.escrow_remaining)}</p>
                        <p className="mt-1 text-xs text-emerald-100/70">The lender takes {Math.round(Number(option.profit_share_percent || 0) * 100)}% of rent from the funded upgrades until {formatMoney(option.max_payout)} is repaid.</p>
                      </div>
                    ))}
                  </div>
                )}

                {dealProfitObligations.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-200">
                      <span className="inline-flex items-center gap-1">
                        <span>Money Still Owed</span>
                        <HelpTooltip content="This is how much more the lender can still collect from the funded upgrades." label="Money still owed help" />
                      </span>
                    </p>
                    {dealProfitObligations.map((obligation) => (
                      <div key={`${obligation.deal_id}-${obligation.tranche_id}`} className="rounded-lg border border-emerald-800/60 bg-gray-900/60 px-3 py-2 text-sm text-emerald-50">
                        <p>{Math.round(Number(obligation.profit_share_percent || 0) * 100)}% of rent from the funded upgrades still goes back to the lender.</p>
                        <p className="mt-1 text-xs text-emerald-100/70">Paid back so far: {formatMoney(obligation.payout_to_date)} / {formatMoney(obligation.max_payout)}</p>
                      </div>
                    ))}
                  </div>
                )}

                {property.deal_trade_warning && (
                  <div className="rounded-lg border border-amber-700/60 bg-amber-950/20 px-3 py-2 text-sm text-amber-100">
                    Trading this property also transfers active deal obligations tied to funded development.
                  </div>
                )}
              </div>
            )}

            {activeTab === 'property' && !isPromptForMe && isOwnedByMe && (
              <div className="rounded-xl border border-gray-700 bg-gray-900/70 p-4 space-y-4">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-xs uppercase tracking-widest text-gray-500">Manage Property</p>
                    <p className="text-sm text-gray-300 mt-1">
                      Develop, sell houses, mortgage, and unmortgage directly from this property card.
                    </p>
                  </div>
                  {property.property_type === 'property' && (
                    <span
                      className={[
                        'px-3 py-1 rounded-full text-xs font-semibold border',
                        (canDevelop || canDevelopWithEscrow) ? 'border-green-700 bg-green-950/40 text-green-300' : 'border-gray-700 bg-gray-800 text-gray-300',
                      ].join(' ')}
                    >
                      {(canDevelop || canDevelopWithEscrow) ? 'Build ready' : 'Build locked'}
                    </span>
                  )}
                </div>

                <div className={`grid gap-3 ${property.property_type === 'property' ? 'grid-cols-3' : 'grid-cols-2'}`}>
                  <button
                    onClick={() => { onDevelop?.(property.board_position); onClose?.(); }}
                    disabled={!canDevelop}
                    className="btn-success"
                  >
                    Develop
                  </button>

                  {property.property_type === 'property' && (
                    <button
                      onClick={() => { onSellHouse?.(property.board_position); onClose?.(); }}
                      disabled={!canSellHouse}
                      className="btn-ghost"
                    >
                      Sell House
                    </button>
                  )}

                  {property.is_mortgaged ? (
                    <button
                      onClick={() => { onUnmortgage?.(property.board_position); onClose?.(); }}
                      disabled={!canUnmortgage}
                      className="btn-primary"
                    >
                      Unmortgage
                    </button>
                  ) : (
                    <button
                      onClick={() => { onMortgage?.(property.board_position); onClose?.(); }}
                      disabled={!canMortgage}
                      className="btn-primary"
                    >
                      Mortgage
                    </button>
                  )}
                </div>

                <div className="space-y-2 text-xs">
                  {property.property_type === 'property' && (
                    <p className={developReason ? 'text-gray-400' : 'text-green-300'}>
                      {developReason || `Build cost: ${formatMoney(developmentCost)}. You can only build on the least-developed property in the set.`}
                    </p>
                  )}
                  {property.property_type === 'property' && canDevelopWithEscrow && (
                    <div className="space-y-2 rounded-lg border border-emerald-900/60 bg-emerald-950/20 p-3 text-emerald-100">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-300">Build With Investor Escrow</p>
                      <div className="flex flex-wrap gap-2">
                        {escrowBuildOptions.map((option) => (
                          <button
                            key={`${option.deal_id}-${option.clause_id}-develop`}
                            type="button"
                            onClick={() => { onDevelop?.(property.board_position, { use_deal_escrow: true, deal_clause_id: option.clause_id }); onClose?.(); }}
                            className="btn-success btn-sm"
                          >
                            Use {formatMoney(option.escrow_remaining)} escrow
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  {property.property_type === 'property' && (
                    <p className={sellReason ? 'text-gray-400' : 'text-yellow-200'}>
                      {sellReason || `Sell refund: ${formatMoney(sellRefund)}. Houses must also be sold evenly across the set.`}
                    </p>
                  )}
                  <p className={(property.is_mortgaged ? unmortgageReason : mortgageReason) ? 'text-gray-400' : 'text-blue-200'}>
                    {property.is_mortgaged
                      ? (unmortgageReason || `Unmortgage cost: ${formatMoney(unmortgageCost)}.`)
                      : (mortgageReason || `Mortgage value: ${formatMoney(mortgageValue)}.`)}
                  </p>
                </div>
              </div>
            )}

            {activeTab === 'property' && !isPromptForMe && !isOwnedByMe && (
              <p className="text-sm text-gray-400 text-center xl:text-left">
                {owner
                  ? `${owner.username} currently controls this property.`
                  : corporateOwner
                    ? `${corporateOwner.name || corporateOwner.stock_symbol || 'A corporation'} controls this land. Corporate spaces are not normal unowned purchases.`
                    : 'You can inspect this property here, and buy it when you land on it.'}
              </p>
            )}

            {activeTab === 'plot' && hasPlotTab && !isPromptForMe && (
              <div className="space-y-4">
                <div className="rounded-xl border border-rose-900/50 bg-rose-950/20 p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-xs uppercase tracking-widest text-rose-300">Local Plot Context</p>
                      <p className="mt-1 text-sm text-rose-100/80">
                        {propertyIsSeized
                          ? 'This property is already part of the revolution. Use actions here to harden control or roll it back.'
                          : 'This property can be pressured locally from here.'}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={onOpenPlotPanel}
                      className="btn-ghost btn-sm"
                    >
                      Open Plot Panel
                    </button>
                  </div>

                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    <div className="rounded-lg border border-rose-900/40 bg-gray-950/40 p-3 text-sm text-gray-100">
                      <p className="text-[11px] uppercase tracking-[0.18em] text-rose-200/70">Property Pressure</p>
                      <p className="mt-2 text-lg font-semibold text-white">{Number(socialProperty.plot_agitation || legalTarget?.agitation || 0)}</p>
                      <p className="mt-1 text-xs text-gray-400">Agitation on this property</p>
                    </div>
                    <div className="rounded-lg border border-rose-900/40 bg-gray-950/40 p-3 text-sm text-gray-100">
                      <p className="text-[11px] uppercase tracking-[0.18em] text-rose-200/70">Control State</p>
                      <p className="mt-2 text-lg font-semibold text-white">
                        {propertyIsSeized ? `Reintegration ${Number(seizedEntry?.reintegration_progress || 0)}%` : legalTarget ? `Seizure score ${Number(legalTarget.preview_score || 0)}` : 'No direct local action'}
                      </p>
                      <p className="mt-1 text-xs text-gray-400">
                        {propertyIsSeized ? `Entrenchment ${Number(seizedEntry?.entrenchment || 0)} • Yield ${Number(seizedEntry?.supply_yield || 0)}` : 'Pressure it locally, then handle global coordination from the plot panel.'}
                      </p>
                    </div>
                  </div>
                </div>

                {plotStatus ? (
                  <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
                    {plotStatus}
                  </div>
                ) : null}

                {revolutionaryActions.length > 0 ? (
                  <div className="rounded-xl border border-gray-700 bg-gray-900/70 p-4 space-y-3">
                    <div>
                      <p className="text-xs uppercase tracking-widest text-gray-500">Revolutionary Actions</p>
                      <p className="mt-1 text-sm text-gray-300">Chose various actions for this specific territory.</p>
                    </div>
                    <div className="space-y-3">
                      {revolutionaryActions.map((action) => {
                        const ui = PLOT_ACTION_UI[action.action_type] || {};
                        return (
                          <div key={action.action_type} className="rounded-lg border border-gray-700 bg-gray-800/80 p-3">
                            <div className="flex items-start justify-between gap-4">
                              <div>
                                <p className="text-sm font-semibold text-white">{ui.title || action.label}</p>
                                <p className="mt-1 text-xs text-gray-400">{ui.summary || action.description}</p>
                              </div>
                              <span className="rounded-full border border-gray-600 px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-200">
                                {formatPlotCost(action)}
                              </span>
                            </div>
                            <button
                              type="button"
                              disabled={plotSubmitting}
                              onClick={() => runPlotLocalAction(onPlotAction, { action_type: action.action_type, property_id: property.id })}
                              className="btn-danger btn-sm mt-3"
                            >
                              {ui.title || action.label}
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : null}

                {counterplayActions.length > 0 ? (
                  <div className="rounded-xl border border-cyan-900/40 bg-cyan-950/10 p-4 space-y-3">
                    <div>
                      <p className="text-xs uppercase tracking-widest text-cyan-300">Counterplay Actions</p>
                      <p className="mt-1 text-sm text-cyan-100/80">These are the local anti-plot tools worth using on this property. Global coalition moves stay in the plot panel.</p>
                    </div>

                    {(counterplayActions.some((action) => action.cash_cost > 0) || counterplayActions.some((action) => action.supporters_required > 0)) && coalitionSupporters.length > 0 ? (
                      <div className="rounded-lg border border-cyan-900/40 bg-gray-950/40 p-3 space-y-3">
                        <label className="flex items-center gap-3 text-sm text-cyan-50">
                          <input
                            type="checkbox"
                            checked={shareCounterFunding}
                            onChange={(event) => setShareCounterFunding(event.target.checked)}
                            className="h-4 w-4 rounded border-gray-600 bg-gray-950 text-cyan-400"
                          />
                          Pool the cash cost with selected coalition members
                        </label>
                        <div className="flex flex-wrap gap-2">
                          {coalitionSupporters.map((supporter) => {
                            const checked = selectedCoalitionSupporters.includes(supporter.id);
                            return (
                              <label key={supporter.id} className="inline-flex items-center gap-2 rounded-full border border-cyan-900/40 px-3 py-2 text-xs text-cyan-50">
                                <input
                                  type="checkbox"
                                  checked={checked}
                                  onChange={(event) => {
                                    setSelectedCoalitionSupporters((current) => (
                                      event.target.checked
                                        ? [...current, supporter.id]
                                        : current.filter((value) => value !== supporter.id)
                                    ));
                                  }}
                                  className="h-3.5 w-3.5 rounded border-gray-600 bg-gray-950 text-cyan-400"
                                />
                                {supporter.username}
                              </label>
                            );
                          })}
                        </div>
                      </div>
                    ) : null}

                    <div className="space-y-3">
                      {counterplayActions.map((action) => {
                        const ui = PLOT_ACTION_UI[action.action_type] || {};
                        return (
                          <div key={action.action_type} className="rounded-lg border border-cyan-900/40 bg-gray-800/80 p-3">
                            <div className="flex items-start justify-between gap-4">
                              <div>
                                <p className="text-sm font-semibold text-white">{ui.title || action.label}</p>
                                <p className="mt-1 text-xs text-gray-400">{ui.summary || action.description}</p>
                              </div>
                              <span className="rounded-full border border-cyan-900/40 px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-cyan-50">
                                {formatPlotCost(action)}
                              </span>
                            </div>
                            <button
                              type="button"
                              disabled={plotSubmitting}
                              onClick={() => runPlotLocalAction(onPlotCounterAction, buildCounterPayload(action))}
                              className="btn-primary btn-sm mt-3"
                            >
                              {ui.title || action.label}
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : null}

                {revolutionaryActions.length === 0 && counterplayActions.length === 0 ? (
                  <div className="rounded-xl border border-gray-700 bg-gray-900/70 p-4 text-sm text-gray-300">
                    No property-specific plot or counterplay action is available here right now. Use the plot panel for region-wide actions and recruitment.
                  </div>
                ) : null}
              </div>
            )}
          </div>
        </div>

        {isPromptForMe && (
          <>
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="text-gray-400">Prompt</span>
              <span className="text-white font-medium">{isCorporatePrompt ? 'Optional corporate buyout' : 'Waiting on your decision'}</span>
            </div>
            <p className="mb-3 text-sm text-blue-100/80">
              {isCorporatePrompt
                ? `This is corporate land, not an unowned property. You may attempt a buyout from ${corporateOwner?.name || 'the corporation'} for ${formatMoney(corporateBuyoutPrice)} or decline and pay corporate rent immediately.`
                : `Buy this property now for ${formatMoney(property.current_value || property.base_price)}.`}
            </p>
            <div className="w-full bg-gray-800 rounded-full h-1.5 mb-2">
              <div
                className="h-1.5 rounded-full transition-all duration-1000"
                style={{
                  width: `${(timeLeft / 30) * 100}%`,
                  backgroundColor: timeLeft <= 5 ? '#ef4444' : timeLeft <= 15 ? '#f59e0b' : '#3b82f6',
                }}
              />
            </div>
            <p className="text-xs text-gray-500 text-center mb-4">Auto-decline in {timeLeft}s</p>
            <div className="flex gap-3">
              <button
                onClick={onBuy}
                disabled={isCorporatePrompt && !canSubmitCorporateBuyout}
                className="btn-primary flex-1 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isCorporatePrompt
                  ? canSubmitCorporateBuyout
                    ? `Buy Out ${formatMoney(corporateBuyoutPrice)}`
                    : `Cannot Buy Out ${formatMoney(corporateBuyoutPrice)}`
                  : `Buy ${formatMoney(property.current_value || property.base_price)}`}
              </button>
              <button onClick={onDecline} className="btn-ghost flex-1">
                {isCorporatePrompt ? `Decline And Pay ${formatMoney(property.corporate_rent || currentRent)}` : 'Decline'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
