import { useEffect, useMemo, useState } from 'react';
import HelpTooltip from '../Common/HelpTooltip';
import { useGameStore } from '../../hooks/useGameState';
import { formatMoney } from '../../utils/formatters';
import ActiveDealsPanel from './ActiveDealsPanel';
import { normalizeGovernmentType } from '../../utils/gameState';
import {
  buildDraftFromDeal,
  getActivePlayerCount,
  getBuildLoanHeadsUpMultiplier,
  createEmptyDealClause,
  estimateScopeValue,
  formatDealDeadline,
  getEffectiveBuildLoanMaxPayout,
  getClauseLabel,
  getClauseTone,
  getDealCounterpartyId,
  getDealCounterpartyName,
  getPropertiesArray,
  summarizeClause,
} from '../../utils/deals';

function clauseScopeOptions(ownerId, properties) {
  const ownerProperties = getPropertiesArray(properties).filter((property) => property.owner_id === ownerId);
  const groups = [...new Set(ownerProperties.map((property) => property.group_color).filter(Boolean))];
  return { ownerProperties, groups };
}


function deadlineMetricLabel(metric) {
  return {
    beneficiary_landings_on_grantor: 'Receiver lands on payer',
    beneficiary_turns: 'Receiver turns',
    grantor_turns: 'Payer turns',
    full_rounds: 'Full rounds',
    beneficiary_rotations: 'Receiver laps',
  }[metric] || 'Receiver turns';
}


function ClauseBuilder({ clause, index, myPlayerId, counterpartyId, players, properties, onChange, onRemove, privateEquityEnabled }) {
  const clauseType = clause.type;
  const beneficiaryId = clause.beneficiarySide === 'me' ? myPlayerId : counterpartyId;
  const grantorId = clauseType === 'development_investment'
    ? (clause.investorSide === 'me' ? counterpartyId : myPlayerId)
    : (clause.beneficiarySide === 'me' ? counterpartyId : myPlayerId);
  const scopeOwnerId = clauseType === 'development_investment'
    ? (clause.investorSide === 'me' ? counterpartyId : myPlayerId)
    : grantorId;
  const { ownerProperties, groups } = clauseScopeOptions(scopeOwnerId, properties);

  const toggleGroup = (groupColor) => {
    const next = clause.groupColors.includes(groupColor)
      ? clause.groupColors.filter((entry) => entry !== groupColor)
      : [...clause.groupColors, groupColor];
    onChange({ groupColors: next });
  };

  const toggleProperty = (propertyId) => {
    const next = clause.propertyIds.includes(propertyId)
      ? clause.propertyIds.filter((entry) => entry !== propertyId)
      : [...clause.propertyIds, propertyId];
    onChange({ propertyIds: next });
  };

  return (
    <div className="rounded-xl border border-gray-700 bg-gray-800/70 p-4 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-gray-500">Clause {index + 1}</p>
          <p className="mt-1 text-sm font-semibold text-white">{getClauseLabel(clauseType)}</p>
        </div>
        <button type="button" onClick={onRemove} className="btn-ghost btn-sm">Remove</button>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <div>
          <label className="block text-xs font-semibold uppercase tracking-[0.18em] text-gray-500">Clause type</label>
          <select
            value={clauseType}
            onChange={(event) => onChange({ type: event.target.value })}
            className="mt-2 w-full rounded-lg border border-gray-600 bg-gray-900 px-3 py-2 text-sm text-white"
          >
            <option value="rent_immunity">No rent</option>
            <option value="rent_discount">Rent cut</option>
            {privateEquityEnabled && <option value="development_investment">Build loan</option>}
          </select>
        </div>

        {clauseType === 'development_investment' ? (
          <div>
            <label className="block text-xs font-semibold uppercase tracking-[0.18em] text-gray-500">Who puts up the cash</label>
            <select
              value={clause.investorSide}
              onChange={(event) => onChange({ investorSide: event.target.value })}
              className="mt-2 w-full rounded-lg border border-gray-600 bg-gray-900 px-3 py-2 text-sm text-white"
            >
              <option value="me">You pay now</option>
              <option value="them">They pay now</option>
            </select>
          </div>
        ) : (
          <div>
            <label className="block text-xs font-semibold uppercase tracking-[0.18em] text-gray-500">Benefit goes to</label>
            <select
              value={clause.beneficiarySide}
              onChange={(event) => onChange({ beneficiarySide: event.target.value })}
              className="mt-2 w-full rounded-lg border border-gray-600 bg-gray-900 px-3 py-2 text-sm text-white"
            >
              <option value="me">You</option>
              <option value="them">Counterparty</option>
            </select>
          </div>
        )}
      </div>

      {clauseType === 'development_investment' && (
        <div className="rounded-lg border border-amber-900/60 bg-amber-950/20 px-3 py-2 text-xs text-amber-100/80">
          One player pays for another player's upgrades now. In return, the lender gets part of the rent from those funded upgrades until the payback cap is reached.
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        <div>
          <label className="block text-xs font-semibold uppercase tracking-[0.18em] text-gray-500">Deadline metric</label>
          <select
            value={clause.deadlineMetric}
            onChange={(event) => onChange({ deadlineMetric: event.target.value })}
            className="mt-2 w-full rounded-lg border border-gray-600 bg-gray-900 px-3 py-2 text-sm text-white"
          >
            <option value="beneficiary_landings_on_grantor">When receiver lands on payer</option>
            <option value="beneficiary_turns">Receiver turns</option>
            <option value="grantor_turns">Payer turns</option>
            <option value="full_rounds">Full rounds</option>
            <option value="beneficiary_rotations">Receiver laps</option>
          </select>
        </div>
        <div>
          <label className="block text-xs font-semibold uppercase tracking-[0.18em] text-gray-500">Amount</label>
          <input
            type="number"
            min={1}
            value={clause.deadlineAmount}
            onChange={(event) => onChange({ deadlineAmount: Math.max(1, Number(event.target.value) || 1) })}
            className="mt-2 w-full rounded-lg border border-gray-600 bg-gray-900 px-3 py-2 text-sm text-white"
          />
        </div>
      </div>

      <div>
        <label className="block text-xs font-semibold uppercase tracking-[0.18em] text-gray-500">Scope</label>
        <div className="mt-2 grid gap-2 md:grid-cols-3">
          {[
            { value: 'all_grantor_properties', label: 'All eligible properties' },
            { value: 'selected_group_colors', label: 'Specific groups' },
            { value: 'selected_property_ids', label: 'Specific properties' },
          ].map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => onChange({ scopeMode: option.value })}
              className={[
                'rounded-lg border px-3 py-2 text-xs font-semibold transition',
                clause.scopeMode === option.value
                  ? 'border-cyan-500 bg-cyan-950/20 text-cyan-100'
                  : 'border-gray-700 bg-gray-900 text-gray-300 hover:border-gray-500',
              ].join(' ')}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {clause.scopeMode === 'selected_group_colors' && (
        <div>
          <p className="text-xs text-gray-500">Choose property groups currently owned by the clause grantor.</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {groups.length === 0 && <span className="text-xs text-gray-500">No eligible groups right now.</span>}
            {groups.map((groupColor) => (
              <button
                key={groupColor}
                type="button"
                onClick={() => toggleGroup(groupColor)}
                className={[
                  'rounded-full border px-3 py-1 text-xs font-semibold transition',
                  clause.groupColors.includes(groupColor)
                    ? 'border-cyan-500 bg-cyan-950/20 text-cyan-100'
                    : 'border-gray-700 bg-gray-900 text-gray-300',
                ].join(' ')}
              >
                <span className="mr-2 inline-block h-2.5 w-2.5 rounded-full align-middle" style={{ backgroundColor: groupColor }} />
                {groupColor}
              </button>
            ))}
          </div>
        </div>
      )}

      {clause.scopeMode === 'selected_property_ids' && (
        <div>
          <p className="text-xs text-gray-500">Choose exact properties currently covered by the clause scope.</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {ownerProperties.length === 0 && <span className="text-xs text-gray-500">No eligible properties right now.</span>}
            {ownerProperties.map((property) => (
              <button
                key={property.id}
                type="button"
                onClick={() => toggleProperty(property.id)}
                className={[
                  'rounded-full border px-3 py-1 text-xs font-semibold transition',
                  clause.propertyIds.includes(property.id)
                    ? 'border-cyan-500 bg-cyan-950/20 text-cyan-100'
                    : 'border-gray-700 bg-gray-900 text-gray-300',
                ].join(' ')}
              >
                {property.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {clauseType === 'rent_discount' && (
        <div>
          <label className="block text-xs font-semibold uppercase tracking-[0.18em] text-gray-500">Rent multiplier</label>
          <input
            type="number"
            min={0.1}
            max={0.9}
            step={0.05}
            value={clause.rentMultiplier}
            onChange={(event) => onChange({ rentMultiplier: Math.min(0.9, Math.max(0.1, Number(event.target.value) || 0.5)) })}
            className="mt-2 w-full rounded-lg border border-gray-600 bg-gray-900 px-3 py-2 text-sm text-white"
          />
          <p className="mt-1 text-xs text-gray-500">0.50 means the beneficiary pays half rent.</p>
        </div>
      )}

      {clauseType === 'development_investment' && (
        <div className="grid gap-3 md:grid-cols-3">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-[0.18em] text-gray-500">
              <span className="inline-flex items-center gap-1">
                <span>Cash up front</span>
                <HelpTooltip content="Money the lender pays now for the other player to spend on upgrades." label="Cash up front help" />
              </span>
            </label>
            <input
              type="number"
              min={50}
              step={25}
              value={clause.escrowAmount}
              onChange={(event) => onChange({ escrowAmount: Math.max(50, Number(event.target.value) || 300) })}
              className="mt-2 w-full rounded-lg border border-gray-600 bg-gray-900 px-3 py-2 text-sm text-white"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase tracking-[0.18em] text-gray-500">
              <span className="inline-flex items-center gap-1">
                <span>Rent share</span>
                <HelpTooltip content="The share of rent from the funded upgrades that goes back to the lender until the cap is reached." label="Rent share help" />
              </span>
            </label>
            <input
              type="number"
              min={0.1}
              max={0.9}
              step={0.05}
              value={clause.profitSharePercent}
              onChange={(event) => onChange({ profitSharePercent: Math.min(0.9, Math.max(0.1, Number(event.target.value) || 0.35)) })}
              className="mt-2 w-full rounded-lg border border-gray-600 bg-gray-900 px-3 py-2 text-sm text-white"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase tracking-[0.18em] text-gray-500">
              <span className="inline-flex items-center gap-1">
                <span>Payback cap</span>
                <HelpTooltip content="The maximum total amount the lender can get back before this build loan ends." label="Payback cap help" />
              </span>
            </label>
            <input
              type="number"
              min={50}
              step={25}
              value={clause.maxPayout}
              onChange={(event) => onChange({ maxPayout: Math.max(50, Number(event.target.value) || 450) })}
              className="mt-2 w-full rounded-lg border border-gray-600 bg-gray-900 px-3 py-2 text-sm text-white"
            />
          </div>
        </div>
      )}

      <div className="rounded-lg border border-gray-700 bg-gray-900/80 px-3 py-2 text-xs text-gray-400">
        Applies to: {players.find((player) => player.id === scopeOwnerId)?.username || 'Unknown'}'s properties • Ends after: {deadlineMetricLabel(clause.deadlineMetric)}
      </div>
    </div>
  );
}


function buildScopeFromClause(clause) {
  if (clause.scopeMode === 'selected_group_colors') {
    return { mode: clause.scopeMode, group_colors: clause.groupColors };
  }
  if (clause.scopeMode === 'selected_property_ids') {
    return { mode: clause.scopeMode, property_ids: clause.propertyIds };
  }
  return { mode: 'all_grantor_properties' };
}


function getClauseScopeOwnerId(clause, myPlayerId, counterpartyId) {
  if (clause.type === 'development_investment') {
    return clause.investorSide === 'me' ? counterpartyId : myPlayerId;
  }
  return clause.beneficiarySide === 'me' ? counterpartyId : myPlayerId;
}


function getInvestmentInvestorId(clause, myPlayerId, counterpartyId) {
  return clause.investorSide === 'me' ? myPlayerId : counterpartyId;
}


function validateClauseDraft(clause, index, myPlayerId, counterpartyId, players, properties) {
  const scopeOwnerId = getClauseScopeOwnerId(clause, myPlayerId, counterpartyId);
  const { ownerProperties, groups } = clauseScopeOptions(scopeOwnerId, properties);

  if (clause.scopeMode === 'selected_group_colors') {
    if (!clause.groupColors.length) {
      return `Clause ${index}: choose at least one property group.`;
    }
    const validGroups = new Set(groups);
    if (clause.groupColors.some((groupColor) => !validGroups.has(groupColor))) {
      return `Clause ${index}: update the selected groups for the current deal layout.`;
    }
  }

  if (clause.scopeMode === 'selected_property_ids') {
    if (!clause.propertyIds.length) {
      return `Clause ${index}: choose at least one property.`;
    }
    const validPropertyIds = new Set(ownerProperties.map((property) => property.id));
    if (clause.propertyIds.some((propertyId) => !validPropertyIds.has(propertyId))) {
      return `Clause ${index}: update the selected properties for the current deal layout.`;
    }
  }

  if (clause.type === 'rent_discount') {
    const rentMultiplier = Number(clause.rentMultiplier || 0);
    if (rentMultiplier < 0.1 || rentMultiplier > 0.9) {
      return `Clause ${index}: rent discounts must stay between 10% and 90%.`;
    }
  }

  if (clause.type === 'development_investment') {
    const investorId = getInvestmentInvestorId(clause, myPlayerId, counterpartyId);
    const investor = players.find((player) => player.id === investorId);
    const escrowAmount = Number(clause.escrowAmount || 0);
    const profitSharePercent = Number(clause.profitSharePercent || 0);
    const maxPayout = Number(clause.maxPayout || 0);

    if (escrowAmount <= 0) {
      return `Clause ${index}: build-loan cash must be more than $0.`;
    }
    if ((Number(investor?.balance || 0) || 0) < escrowAmount) {
      return `Clause ${index}: ${investor?.username || 'The lender'} cannot currently front ${formatMoney(escrowAmount)}.`;
    }
    if (profitSharePercent <= 0 || profitSharePercent >= 1) {
      return `Clause ${index}: rent share must stay between 10% and 90%.`;
    }
    if (maxPayout <= 0) {
      return `Clause ${index}: payback cap must be more than $0.`;
    }
  }

  return null;
}


function estimateClauseImpact(clause, myPlayerId, counterpartyId, properties, economy) {
  const deadlineAmount = Number(clause.deadlineAmount || 1) || 1;
  if (clause.type === 'development_investment') {
    const investorId = clause.investorSide === 'me' ? myPlayerId : counterpartyId;
    const recipientId = clause.investorSide === 'me' ? counterpartyId : myPlayerId;
    return {
      me: investorId === myPlayerId
        ? Math.max(0, Number(clause.maxPayout || 0) - Number(clause.escrowAmount || 0))
        : Number(clause.escrowAmount || 0) * 0.85,
      them: investorId === myPlayerId
        ? Number(clause.escrowAmount || 0) * 0.85
        : Math.max(0, Number(clause.maxPayout || 0) - Number(clause.escrowAmount || 0)),
      scopeLabel: recipientId,
    };
  }

  const grantorId = clause.beneficiarySide === 'me' ? counterpartyId : myPlayerId;
  const beneficiaryId = clause.beneficiarySide === 'me' ? myPlayerId : counterpartyId;
  const scope = buildScopeFromClause(clause);
  const multiplier = clause.type === 'rent_discount'
    ? (1 - Number(clause.rentMultiplier || 0.5))
    : 1;
  const value = estimateScopeValue(scope, grantorId, properties, deadlineAmount, multiplier, economy);

  return {
    me: beneficiaryId === myPlayerId ? value : -value,
    them: beneficiaryId === counterpartyId ? value : -value,
  };
}


export default function DealDeskModal({ myPlayerId, onSubmit, onRespond, onCounter, onCancel, onClose }) {
  const { activeDeal, clearActiveDeal, deals, players, properties, settings, economy, setActiveDeal, saveTradeDealDraft } = useGameStore();
  const [title, setTitle] = useState('');
  const [targetPlayerId, setTargetPlayerId] = useState('');
  const [clauses, setClauses] = useState([createEmptyDealClause()]);
  const [editingCounterId, setEditingCounterId] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const others = players.filter((player) => player.id !== myPlayerId && !player.bankrupt);
  const privateEquityEnabled = settings?.private_equity_enabled !== false;
  const dealsEnabled = settings?.deals_enabled !== false;
  const selectedDeal = activeDeal || null;
  const selectedCounterpartyId = selectedDeal ? getDealCounterpartyId(selectedDeal, myPlayerId) : null;
  const selectedCounterpartyName = selectedDeal ? getDealCounterpartyName(selectedDeal, myPlayerId, players) : null;
  const governmentType = normalizeGovernmentType(economy?.gov_type || economy?.government_type || settings?.government_type || 'liberal_democracy');
  const isLiberalDemocracy = governmentType === 'liberal_democracy';
  const marketConfidence = Number(economy?.market_confidence || 0);
  const capitalYieldRate = Number(economy?.capital_yield_rate || 0);
  const capitalYieldReserveFloor = Math.max(0, Number(economy?.capital_yield_reserve_floor || settings?.go_salary || 200));
  const privateEquityBonus = Math.max(1, Number(economy?.private_equity_bonus_multiplier || 1));
  const buildLoanBonusPercent = Math.max(0, (privateEquityBonus - 1) * 100);
  const activePlayerCount = getActivePlayerCount(players);
  const headsUpBuildLoanBonusPercent = Math.max(0, (getBuildLoanHeadsUpMultiplier(activePlayerCount) - 1) * 100);
  const terminationRequestedById = selectedDeal?.termination_requested_by_id ?? null;
  const terminationRequestedByMe = terminationRequestedById != null && terminationRequestedById === myPlayerId;
  const terminationRequestedByOther = terminationRequestedById != null && terminationRequestedById !== myPlayerId;
  const terminationRequesterName = terminationRequestedByMe
    ? 'You'
    : (selectedDeal?.termination_requested_by_name || players.find((player) => player.id === terminationRequestedById)?.username || 'The other party');

  useEffect(() => {
    if (!targetPlayerId && others[0]?.id != null) {
      setTargetPlayerId(String(others[0].id));
    }
  }, [others, targetPlayerId]);

  useEffect(() => () => clearActiveDeal(), [clearActiveDeal]);

  const valuePreview = useMemo(() => {
    const counterpartyId = Number(targetPlayerId || 0) || null;
    if (!counterpartyId) {
      return { me: 0, them: 0 };
    }

    return clauses.reduce(
      (totals, clause) => {
        const impact = estimateClauseImpact(clause, myPlayerId, counterpartyId, properties, economy);
        return {
          me: totals.me + impact.me,
          them: totals.them + impact.them,
        };
      },
      { me: 0, them: 0 },
    );
  }, [clauses, economy, myPlayerId, properties, targetPlayerId]);

  const submitLabel = editingCounterId ? 'Send Counteroffer' : 'Propose Deal';

  const resetBuilder = () => {
    setTitle('');
    setClauses([createEmptyDealClause()]);
    setEditingCounterId(null);
    setError('');
    setNotice('');
  };

  const loadCounterDraft = () => {
    if (!selectedDeal) {
      return;
    }
    const draft = buildDraftFromDeal(selectedDeal, myPlayerId);
    setTitle(draft.title || 'Counteroffer');
    setTargetPlayerId(String(draft.counterpartyId || ''));
    setClauses(draft.clauses.length ? draft.clauses : [createEmptyDealClause()]);
    setEditingCounterId(selectedDeal.id);
    setError('');
    setNotice('');
  };

  const buildDealPayload = (counterpartyId) => ({
    title: title.trim() || undefined,
    counterparty_id: counterpartyId,
    clauses: clauses.map((clause) => {
      const deadline = {
        metric: clause.deadlineMetric,
        initial: Number(clause.deadlineAmount || 1) || 1,
      };

      if (clause.type === 'development_investment') {
        const investorId = clause.investorSide === 'me' ? myPlayerId : counterpartyId;
        const recipientId = clause.investorSide === 'me' ? counterpartyId : myPlayerId;
        return {
          type: clause.type,
          investor_id: investorId,
          recipient_id: recipientId,
          scope: buildScopeFromClause(clause),
          config: {
            escrow_amount: Number(clause.escrowAmount || 0),
            profit_share_percent: Number(clause.profitSharePercent || 0),
            max_payout: Number(clause.maxPayout || 0),
          },
          deadline,
        };
      }

      const beneficiaryId = clause.beneficiarySide === 'me' ? myPlayerId : counterpartyId;
      const grantorId = clause.beneficiarySide === 'me' ? counterpartyId : myPlayerId;
      return {
        type: clause.type,
        grantor_id: grantorId,
        beneficiary_id: beneficiaryId,
        scope: buildScopeFromClause(clause),
        config: clause.type === 'rent_discount'
          ? { rent_multiplier: Number(clause.rentMultiplier || 0.5) }
          : {},
        deadline,
      };
    }),
  });

  const saveDraftForTrade = () => {
    setError('');
    setNotice('');

    const counterpartyId = Number(targetPlayerId || 0);
    if (!dealsEnabled) {
      setError('Deals are disabled in this match.');
      return;
    }
    if (!counterpartyId) {
      setError('Choose a counterparty first.');
      return;
    }
    if (!clauses.length) {
      setError('Add at least one clause.');
      return;
    }

    for (const [index, clause] of clauses.entries()) {
      const clauseError = validateClauseDraft(clause, index + 1, myPlayerId, counterpartyId, players, properties);
      if (clauseError) {
        setError(clauseError);
        return;
      }
    }

    const payload = buildDealPayload(counterpartyId);
    saveTradeDealDraft({
      title: payload.title || 'Untitled deal draft',
      counterparty_id: payload.counterparty_id,
      clauses: payload.clauses,
      payload,
      created_by_player_id: myPlayerId,
      updated_at: new Date().toISOString(),
    });
    setNotice('Draft saved for trade attachments.');
  };

  const submitDeal = async () => {
    setError('');
    setNotice('');
    if (isSubmitting) {
      return;
    }

    const counterpartyId = Number(targetPlayerId || 0);
    if (!dealsEnabled) {
      setError('Deals are disabled in this match.');
      return;
    }
    if (!counterpartyId) {
      setError('Choose a counterparty first.');
      return;
    }
    if (!clauses.length) {
      setError('Add at least one clause.');
      return;
    }

    for (const [index, clause] of clauses.entries()) {
      const clauseError = validateClauseDraft(clause, index + 1, myPlayerId, counterpartyId, players, properties);
      if (clauseError) {
        setError(clauseError);
        return;
      }
    }

    const payload = buildDealPayload(counterpartyId);

    const submitAction = editingCounterId ? onCounter : onSubmit;
    if (!submitAction) {
      setError('Deal actions are unavailable right now.');
      return;
    }

    setIsSubmitting(true);
    try {
      const result = editingCounterId
        ? await submitAction(editingCounterId, payload)
        : await submitAction(payload);
      if (result?.deal) {
        setActiveDeal(result.deal);
      }
      resetBuilder();
    } catch (submitError) {
      setError(submitError?.message || 'Failed to send the deal.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="flex max-h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-gray-700 bg-gray-900 shadow-2xl">
        <div className="flex items-center justify-between border-b border-gray-700 px-5 py-4">
          <div>
            <h2 className="text-lg font-bold text-white">Deals Desk</h2>
            <p className="mt-1 text-sm text-gray-400">Build explicit contracts, review incoming proposals, and track active obligations.</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => {
                resetBuilder();
                clearActiveDeal();
              }}
              className="btn-ghost btn-sm"
            >
              New Draft
            </button>
            <button type="button" onClick={onClose} className="text-xl text-gray-400 transition hover:text-white">X</button>
          </div>
        </div>

        <div className="grid flex-1 overflow-hidden lg:grid-cols-[1.2fr_0.8fr]">
          <div className="overflow-y-auto p-5 space-y-5">
            {selectedDeal && (
              <div className="rounded-2xl border border-gray-700 bg-gray-800/70 p-4 space-y-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-gray-500">Selected deal</p>
                    <h3 className="mt-1 text-xl font-semibold text-white">{selectedCounterpartyName}</h3>
                    <p className="mt-1 text-sm text-gray-400">{selectedDeal.title || 'Untitled deal'} • status: {selectedDeal.status}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {selectedDeal.clauses.map((clause) => (
                      <span key={`${selectedDeal.id}-${clause.id}-chip`} className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${getClauseTone(clause.type)}`}>
                        {getClauseLabel(clause.type)}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="space-y-3">
                  {selectedDeal.clauses.map((clause) => (
                    <div key={`${selectedDeal.id}-${clause.id}-detail`} className="rounded-xl border border-gray-700 bg-gray-900/80 px-3 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-semibold text-white">{getClauseLabel(clause.type)}</p>
                        <span className="text-xs text-gray-400">{formatDealDeadline(clause.deadline)}</span>
                      </div>
                      <p className="mt-2 text-sm text-gray-300">{summarizeClause(clause, myPlayerId, players, properties, economy)}</p>
                      {isLiberalDemocracy && clause.type === 'development_investment' && (
                        <p className="mt-2 text-xs text-emerald-200/80">
                          Current build-loan bonus: this deal can pay back up to about {formatMoney(getEffectiveBuildLoanMaxPayout(Number(clause.config?.max_payout || 0), privateEquityBonus, activePlayerCount))}.
                        </p>
                      )}
                    </div>
                  ))}
                </div>

                {selectedDeal.status === 'accepted' && terminationRequestedById && (
                  <div className="rounded-xl border border-amber-700/60 bg-amber-950/20 px-3 py-3 text-sm text-amber-100">
                    {terminationRequestedByMe
                      ? `Termination requested. Waiting for ${selectedCounterpartyName || 'the other party'} to confirm.`
                      : `${terminationRequesterName} requested termination. Confirm to end the deal.`}
                  </div>
                )}

                <div className="flex flex-wrap gap-2">
                  {selectedDeal.status === 'proposed' && selectedDeal.counterparty_id === myPlayerId && (
                    <>
                      <button type="button" onClick={() => onRespond?.(selectedDeal.id, 'accept')} className="btn-success">Accept</button>
                      <button type="button" onClick={() => onRespond?.(selectedDeal.id, 'reject')} className="btn-danger">Reject</button>
                      <button type="button" onClick={loadCounterDraft} className="btn-ghost">Counter</button>
                    </>
                  )}
                  {selectedDeal.status === 'proposed' && selectedDeal.proposer_id === myPlayerId && (
                    <button type="button" onClick={() => onCancel?.(selectedDeal.id)} className="btn-danger">Cancel Proposal</button>
                  )}
                  {selectedDeal.status === 'accepted' && (
                    <button
                      type="button"
                      onClick={() => onCancel?.(selectedDeal.id)}
                      disabled={terminationRequestedByMe}
                      className={`btn-ghost ${terminationRequestedByMe ? 'cursor-not-allowed opacity-60' : ''}`}
                    >
                      {terminationRequestedByOther ? 'Confirm Termination' : terminationRequestedByMe ? 'Termination Requested' : 'Request Termination'}
                    </button>
                  )}
                  {selectedDeal.status !== 'proposed' && (
                    <button type="button" onClick={loadCounterDraft} className="btn-ghost">Use As Counter Draft</button>
                  )}
                </div>
              </div>
            )}

            <div className="rounded-2xl border border-gray-700 bg-gray-800/70 p-4 space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-gray-500">Deal Builder</p>
                  <h3 className="mt-1 text-xl font-semibold text-white">{editingCounterId ? 'Counteroffer Draft' : 'New Proposal'}</h3>
                </div>
                <div className="rounded-xl border border-gray-700 bg-gray-900/80 px-3 py-2 text-xs text-gray-300">
                  <p>You: {formatMoney(valuePreview.me)}</p>
                  <p>Them: {formatMoney(valuePreview.them)}</p>
                </div>
              </div>

              {isLiberalDemocracy && (
                <div className="rounded-xl border border-cyan-900/60 bg-cyan-950/20 px-3 py-3 text-xs text-cyan-100">
                  <div className="flex items-center gap-2">
                    <p className="font-semibold uppercase tracking-[0.18em] text-cyan-300">This Round's Cash Rules</p>
                    <HelpTooltip
                      label="Cash rules help"
                      content={`Investor Mood changes cash bonuses and build loan returns. Cash Bonus pays on money you keep above ${formatMoney(capitalYieldReserveFloor)}. Build Loan Bonus raises the payback cap on build loans.${activePlayerCount === 2 ? ` A 1v1 bonus is also active, adding another ${headsUpBuildLoanBonusPercent.toFixed(0)}% because you are funding your only rival.` : ''}`}
                    />
                  </div>
                  <div className="mt-3 space-y-2">
                    <div className="flex items-center justify-between gap-3">
                      <span className="inline-flex items-center gap-1 text-cyan-100/80">
                        <span>Investor Mood</span>
                        <HelpTooltip content="Higher Investor Mood increases cash bonuses and build loan payback caps." label="Investor Mood help" />
                      </span>
                      <span className="font-mono text-cyan-50">{marketConfidence.toFixed(1)}/100</span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span className="inline-flex items-center gap-1 text-cyan-100/80">
                        <span>Cash Bonus</span>
                        <HelpTooltip content={`At round end, cash kept above ${formatMoney(capitalYieldReserveFloor)} earns this bonus.`} label="Cash Bonus help" />
                      </span>
                      <span className="font-mono text-cyan-50">{(capitalYieldRate * 100).toFixed(2)}%</span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span className="inline-flex items-center gap-1 text-cyan-100/80">
                        <span>Build Loan Bonus</span>
                        <HelpTooltip content="This increases the maximum total payback on build loans this round." label="Build Loan Bonus help" />
                      </span>
                      <span className="font-mono text-cyan-50">+{buildLoanBonusPercent.toFixed(0)}%</span>
                    </div>
                  </div>
                  {activePlayerCount === 2 && (
                    <p className="mt-2 text-cyan-100/70">1v1 bonus active: build loans can pay back another {headsUpBuildLoanBonusPercent.toFixed(0)}% because you are funding your only rival.</p>
                  )}
                </div>
              )}

              {isLiberalDemocracy && clauses.some((clause) => clause.type === 'development_investment') && (
                <div className="rounded-xl border border-emerald-900/60 bg-emerald-950/20 px-3 py-3 text-xs text-emerald-100">
                  <div className="flex items-center gap-2">
                    <p className="font-semibold uppercase tracking-[0.18em] text-emerald-300">Max Payback Right Now</p>
                    <HelpTooltip content="This is the most the lender can get back from each build loan under the current bonuses." label="Max payback help" />
                  </div>
                  <div className="mt-2 space-y-1">
                    {clauses.map((clause, index) => (
                      clause.type === 'development_investment' ? (
                        <p key={clause.key}>Clause {index + 1} can pay back up to {formatMoney(getEffectiveBuildLoanMaxPayout(Number(clause.maxPayout || 0), privateEquityBonus, activePlayerCount))} right now.</p>
                      ) : null
                    ))}
                  </div>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold uppercase tracking-[0.18em] text-gray-500">Title</label>
                <input
                  type="text"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="Optional short title"
                  className="mt-2 w-full rounded-lg border border-gray-600 bg-gray-900 px-3 py-2 text-sm text-white"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-[0.18em] text-gray-500">Other player</label>
                <select
                  value={targetPlayerId}
                  onChange={(event) => setTargetPlayerId(event.target.value)}
                  className="mt-2 w-full rounded-lg border border-gray-600 bg-gray-900 px-3 py-2 text-sm text-white"
                >
                  {others.length === 0 && <option value="">No eligible players</option>}
                  {others.map((player) => (
                    <option key={player.id} value={player.id}>{player.username}</option>
                  ))}
                </select>
              </div>

              <div className="space-y-3">
                {clauses.map((clause, index) => (
                  <ClauseBuilder
                    key={clause.key}
                    clause={clause}
                    index={index}
                    myPlayerId={myPlayerId}
                    counterpartyId={Number(targetPlayerId || 0)}
                    players={players}
                    properties={properties}
                    privateEquityEnabled={privateEquityEnabled}
                    onChange={(updates) => setClauses((previous) => previous.map((entry) => (entry.key === clause.key ? { ...entry, ...updates } : entry)))}
                    onRemove={() => setClauses((previous) => (previous.length > 1 ? previous.filter((entry) => entry.key !== clause.key) : previous))}
                  />
                ))}
              </div>

              <div className="flex flex-wrap gap-2">
                <button type="button" onClick={() => setClauses((previous) => [...previous, createEmptyDealClause()])} className="btn-ghost">
                  Add Clause
                </button>
                <button type="button" onClick={saveDraftForTrade} className="btn-ghost" disabled={!others.length || isSubmitting}>
                  Save For Trade
                </button>
                <button type="button" onClick={submitDeal} className="btn-primary" disabled={!others.length || isSubmitting}>
                  {isSubmitting ? 'Sending...' : submitLabel}
                </button>
              </div>

              {notice && <p className="text-sm text-emerald-400">{notice}</p>}
              {error && <p className="text-sm text-red-400">{error}</p>}
            </div>
          </div>

          <div className="border-t border-gray-700 p-5 lg:border-l lg:border-t-0 overflow-y-auto">
            <ActiveDealsPanel
              deals={deals}
              players={players}
              properties={properties}
              economy={economy}
              myPlayerId={myPlayerId}
              selectedDealId={selectedDeal?.id}
              onSelect={setActiveDeal}
            />
          </div>
        </div>
      </div>
    </div>
  );
}