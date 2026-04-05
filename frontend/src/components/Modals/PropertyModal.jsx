import { useEffect, useState } from 'react';
import { useGameStore } from '../../hooks/useGameState';
import { formatExactMoney, formatMoney } from '../../utils/formatters';
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
  onClose,
}) {
  const {
    pendingAction,
    myPlayerId,
    currentPlayerId,
    players,
    properties,
    economy,
  } = useGameStore();
  const [timeLeft, setTimeLeft] = useState(30);

  const actionData = data || pendingAction?.data || null;
  const property = resolveLiveProperty(propertyProp || actionData?.property, actionData, properties);

  useEffect(() => {
    setTimeLeft(30);
  }, [actionData?.property_id, property?.id, mode]);

  const me = players.find((player) => player.id === myPlayerId) || null;
  const owner = property?.owner_id ? players.find((player) => player.id === property.owner_id) : null;
  const isMyTurn = currentPlayerId === myPlayerId;
  const isOwnedByMe = property?.owner_id === myPlayerId;
  const socialRestrictionReason = property.social_unionized
    ? 'This property is controlled by the Proletariat Union and cannot be privately managed.'
    : null;
  const isPromptForMe = actionData?.player_id === myPlayerId
    && property
    && (actionData?.property_id === property.id || actionData?.position === property.board_position);

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
    : property.is_mortgaged
    ? 'Mortgaged'
    : owner
      ? `Owned by ${owner.username}`
      : 'Unowned';

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
                    {property.social_unionized ? 'Unionized Asset' : `${property.social_incident_type} in progress`}
                  </p>
                  <p className="mt-1 text-xs text-rose-100/80">
                    Tension {Math.round(Number(property.social_tension || 0))} • Territory instability {Math.round(Number(property.social_territory_instability || 0))}
                  </p>
                  {property.social_dominant_grievance && (
                    <p className="mt-1 text-xs text-rose-100/70">
                      Dominant grievance: {property.social_dominant_grievance.replaceAll('_', ' ')}
                    </p>
                  )}
                </div>
              )}
            </div>

            {(dealModifiers.length > 0 || dealInvestmentOptions.length > 0 || dealProfitObligations.length > 0) && (
              <div className="rounded-xl border border-emerald-900/60 bg-emerald-950/20 p-4 space-y-3">
                <div>
                  <p className="text-xs uppercase tracking-widest text-emerald-300">Deal Effects</p>
                  <p className="mt-1 text-sm text-emerald-100/80">This property currently carries active contract modifiers or investment obligations.</p>
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
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-200">Investment-backed Build Options</p>
                    {dealInvestmentOptions.map((option) => (
                      <div key={`${option.deal_id}-${option.clause_id}`} className="rounded-lg border border-emerald-800/60 bg-gray-900/60 px-3 py-2 text-sm text-emerald-50">
                        <p>Escrow available: {formatMoney(option.escrow_remaining)}</p>
                        <p className="mt-1 text-xs text-emerald-100/70">Investor share: {Math.round(Number(option.profit_share_percent || 0) * 100)}% until {formatMoney(option.max_payout)}</p>
                      </div>
                    ))}
                  </div>
                )}

                {dealProfitObligations.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-200">Investor Obligations</p>
                    {dealProfitObligations.map((obligation) => (
                      <div key={`${obligation.deal_id}-${obligation.tranche_id}`} className="rounded-lg border border-emerald-800/60 bg-gray-900/60 px-3 py-2 text-sm text-emerald-50">
                        <p>{Math.round(Number(obligation.profit_share_percent || 0) * 100)}% of funded rent is still owed to an investor.</p>
                        <p className="mt-1 text-xs text-emerald-100/70">Paid out: {formatMoney(obligation.payout_to_date)} / {formatMoney(obligation.max_payout)}</p>
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

            {!isPromptForMe && isOwnedByMe && (
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

            {!isPromptForMe && !isOwnedByMe && (
              <p className="text-sm text-gray-400 text-center xl:text-left">
                {owner
                  ? `${owner.username} currently controls this property.`
                  : 'You can inspect this property here, and buy it when you land on it.'}
              </p>
            )}
          </div>
        </div>

        {isPromptForMe && (
          <>
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="text-gray-400">Prompt</span>
              <span className="text-white font-medium">Waiting on your decision</span>
            </div>
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
              <button onClick={onBuy} className="btn-primary flex-1">
                Buy {formatMoney(property.current_value || property.base_price)}
              </button>
              <button onClick={onDecline} className="btn-ghost flex-1">
                Decline
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
