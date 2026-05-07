import { useEffect, useMemo, useState } from 'react';
import { useGameStore } from '../../hooks/useGameState';
import { formatDealDeadline, summarizeClause } from '../../utils/deals';
import { BOARD_SPACES, needsDarkText } from '../../utils/constants';
import { formatMoney } from '../../utils/formatters';

function resolveTradePropertyIds(positions, properties) {
  return positions.map((position) => properties[position]?.id ?? null);
}

function PropertyChip({ position, onAdd, onRemove, selected, disabled }) {
  const space = BOARD_SPACES.find((s) => s.position === position);
  if (!space) return null;

  return (
    <button
      onClick={() => selected ? onRemove(position) : onAdd(position)}
      disabled={disabled}
      aria-pressed={selected}
      className={[
        'flex items-center gap-1.5 px-2 py-1 rounded-lg border text-xs font-medium transition',
        selected
          ? 'border-blue-500 bg-blue-900/40 text-blue-200'
          : 'border-gray-600 bg-gray-800 text-gray-300 hover:border-gray-400',
        disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer',
      ].join(' ')}
    >
      <div
        className="w-2 h-2 rounded-full flex-shrink-0"
        style={{ backgroundColor: space.groupColor || '#555' }}
      />
      <span>{space.name}</span>
    </button>
  );
}

export default function TradePanel({ myPlayerId, onSubmit, onRespond, onClose }) {
  const { activeTrade, players, properties, settings, economy, lobbyingStats, tradeDealDrafts, deleteTradeDealDraft } = useGameStore();
  const [targetPlayerId, setTargetPlayerId] = useState('');
  const [offerMoney, setOfferMoney] = useState(0);
  const [requestMoney, setRequestMoney] = useState(0);
  const [offerProperties, setOfferProperties] = useState([]);
  const [requestProperties, setRequestProperties] = useState([]);
  const [offerLobbyTarget, setOfferLobbyTarget] = useState('');
  const [offerLobbyAmount, setOfferLobbyAmount] = useState(0);
  const [requestLobbyTarget, setRequestLobbyTarget] = useState('');
  const [requestLobbyAmount, setRequestLobbyAmount] = useState(0);
  const [selectedDraftIds, setSelectedDraftIds] = useState([]);
  const [error, setError] = useState('');

  const me = players.find((p) => p.id === myPlayerId);
  const others = players.filter((p) => p.id !== myPlayerId && !p.bankrupt);
  const target = players.find((p) => p.id === targetPlayerId);
  const govType = economy?.gov_type || settings?.government_type || 'liberal_democracy';
  const availableOfferBalance = Math.max(0, Number(me?.balance || 0));
  const canPledgeLobbying = Boolean(settings?.lobbying_enabled) && (economy?.gov_type || settings?.government_type) !== 'minarchism';
  const policyOptions = useMemo(() => {
    const pools = Object.values(lobbyingStats?.policy_pools || {});
    if (pools.length) {
      return pools.map((pool) => ({
        target: pool.target,
        label: pool.policy_name || pool.target,
      }));
    }

    return [
      { target: 'tax_multiplier_decrease', label: 'Decrease Tax Rate' },
      { target: 'welfare_increase', label: 'Increase Welfare Rate' },
      { target: 'welfare_decrease', label: 'Decrease Welfare Rate' },
      { target: 'tax_multiplier_increase', label: 'Increase Tax Rate' },
      { target: 'stabilization_fund', label: 'Rebuild Treasury' },
      { target: 'economic_stimulus', label: 'Fund Economic Stimulus' },
      ...(govType === 'liberal_democracy'
        ? [
          { target: 'tax_bracket_rate_up', label: 'Raise A Tax Bracket Rate' },
          { target: 'tax_bracket_rate_down', label: 'Lower A Tax Bracket Rate' },
          { target: 'tax_bracket_boundary_up', label: 'Lift A Tax Bracket Threshold' },
          { target: 'tax_bracket_boundary_down', label: 'Lower A Tax Bracket Threshold' },
          { target: 'treasury_transfer_players', label: 'Send Treasury Money To Players' },
          { target: 'treasury_transfer_treasury', label: 'Rebuild Treasury Reserves' },
          { target: 'money_supply_expand', label: 'Expand Money Supply' },
          { target: 'money_supply_contract', label: 'Tighten Money Supply' },
        ]
        : []),
    ];
  }, [govType, lobbyingStats]);

  const myProperties = Object.entries(properties)
    .filter(([_, p]) => p.owner_id === myPlayerId && !p.is_mortgaged)
    .map(([pos]) => Number(pos));

  const targetProperties = targetPlayerId
    ? Object.entries(properties)
        .filter(([_, p]) => p.owner_id === targetPlayerId && !p.is_mortgaged)
        .map(([pos]) => Number(pos))
    : [];

  const tradeToView = activeTrade || null;
  const isReceiver = tradeToView?.receiver_id === myPlayerId;
  const isProposer = tradeToView?.proposer_id === myPlayerId;
  const savedDraftCounterparties = useMemo(() => {
    const grouped = new Map();
    for (const draft of tradeDealDrafts || []) {
      const counterpartyId = Number(draft?.counterparty_id || 0);
      if (!counterpartyId || grouped.has(counterpartyId)) {
        continue;
      }
      grouped.set(counterpartyId, {
        counterpartyId,
        player: players.find((player) => player.id === counterpartyId) || null,
      });
    }
    return Array.from(grouped.values());
  }, [players, tradeDealDrafts]);
  const availableDealDrafts = useMemo(
    () => (tradeDealDrafts || []).filter(
      (draft) => String(draft.counterparty_id) === String(targetPlayerId || ''),
    ),
    [targetPlayerId, tradeDealDrafts],
  );
  const visibleDealDrafts = targetPlayerId ? availableDealDrafts : (tradeDealDrafts || []);

  useEffect(() => {
    if (tradeToView || targetPlayerId || savedDraftCounterparties.length !== 1) {
      return;
    }

    setTargetPlayerId(savedDraftCounterparties[0].counterpartyId);
  }, [savedDraftCounterparties, targetPlayerId, tradeToView]);

  useEffect(() => {
    setSelectedDraftIds((previous) => previous.filter((draftId) => availableDealDrafts.some((draft) => draft.id === draftId)));
  }, [availableDealDrafts]);

  const renderTradeCard = (title, money, tradeProperties, lobbyPledges, accentClass) => (
    <div className="bg-gray-800 rounded-xl p-4">
      <h3 className={`text-sm font-semibold mb-3 ${accentClass}`}>{title}</h3>
      {money > 0 && (
        <p className="font-mono text-lg text-gray-200">{formatMoney(money)}</p>
      )}
      {(tradeProperties || []).map((pos) => {
        const space = BOARD_SPACES.find((s) => s.position === pos);
        return space ? (
          <div key={pos} className="flex items-center gap-2 mt-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: space.groupColor }} />
            <span className="text-gray-300 text-sm">{space.name}</span>
          </div>
        ) : null;
      })}
      {(lobbyPledges || []).map((pledge) => (
        <div key={`${pledge.target}-${pledge.amount}`} className="flex items-center justify-between gap-3 mt-2 rounded-lg border border-fuchsia-900/50 bg-fuchsia-950/20 px-2.5 py-2">
          <span className="text-xs text-fuchsia-100">Lobby: {pledge.policy_name || pledge.target}</span>
          <span className="text-xs font-mono text-fuchsia-300">{formatMoney(pledge.amount)}</span>
        </div>
      ))}
      {!money && !(tradeProperties?.length) && !(lobbyPledges?.length) && (
        <p className="text-gray-500 italic text-sm">Nothing</p>
      )}
    </div>
  );

  const handleSubmit = () => {
    setError('');
    if (!targetPlayerId) return setError('Select a player to trade with');
    if (offerMoney < 0 || requestMoney < 0) return setError('Money cannot be negative');
    if (offerMoney > availableOfferBalance) return setError('You cannot afford this offer');
    if (offerLobbyAmount > 0 && !offerLobbyTarget) return setError('Choose a lobbying target for your pledged contribution');
    if (requestLobbyAmount > 0 && !requestLobbyTarget) return setError('Choose a lobbying target for the other player’s pledged contribution');

    const offeredPropIds = resolveTradePropertyIds(offerProperties, properties);
    const requestedPropIds = resolveTradePropertyIds(requestProperties, properties);
    const offeredLobbyPledges = offerLobbyAmount > 0 && offerLobbyTarget
      ? [{ target: offerLobbyTarget, amount: offerLobbyAmount }]
      : [];
    const requestedLobbyPledges = requestLobbyAmount > 0 && requestLobbyTarget
      ? [{ target: requestLobbyTarget, amount: requestLobbyAmount }]
      : [];

    if (offeredPropIds.some((id) => id == null) || requestedPropIds.some((id) => id == null)) {
      return setError('One or more selected properties could not be resolved');
    }

    const includedDealDrafts = selectedDraftIds
      .map((draftId) => availableDealDrafts.find((draft) => draft.id === draftId)?.payload)
      .filter(Boolean);

    onSubmit({
      receiver_id: targetPlayerId,
      offered_money: offerMoney,
      requested_money: requestMoney,
      offered_props: offeredPropIds,
      requested_props: requestedPropIds,
      offered_lobby_pledges: offeredLobbyPledges,
      requested_lobby_pledges: requestedLobbyPledges,
      included_deal_drafts: includedDealDrafts,
    });
  };

  const addOffer = (pos) => setOfferProperties((prev) => [...prev, pos]);
  const removeOffer = (pos) => setOfferProperties((prev) => prev.filter((p) => p !== pos));
  const addRequest = (pos) => setRequestProperties((prev) => [...prev, pos]);
  const removeRequest = (pos) => setRequestProperties((prev) => prev.filter((p) => p !== pos));

  const toggleDealDraft = (draftId) => {
    setSelectedDraftIds((previous) => (
      previous.includes(draftId)
        ? previous.filter((entry) => entry !== draftId)
        : [...previous, draftId]
    ));
  };

  const selectDealDraft = (draft) => {
    const counterpartyId = Number(draft?.counterparty_id || 0);
    if (!counterpartyId) {
      return;
    }

    if (!targetPlayerId || String(targetPlayerId) !== String(counterpartyId)) {
      setTargetPlayerId(counterpartyId);
      setSelectedDraftIds([draft.id]);
      return;
    }

    toggleDealDraft(draft.id);
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <h2 className="text-lg font-bold text-white">Trade</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition text-xl">X</button>
        </div>

        {tradeToView ? (
          /* Active trade view */
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            <div className="text-center">
              <p className="text-white font-semibold">
                {isReceiver
                  ? `${tradeToView.proposer_name} wants to trade with you!`
                  : isProposer
                    ? `Waiting for ${tradeToView.receiver_name} to respond.`
                    : `${tradeToView.proposer_name} proposed a trade to ${tradeToView.receiver_name}.`}
              </p>
              {!isReceiver && (
                <p className="text-sm text-gray-400 mt-2">
                  Only {tradeToView.receiver_name} can accept or decline this deal.
                </p>
              )}
            </div>
            <div className="grid grid-cols-2 gap-4">
              {renderTradeCard(
                `${tradeToView.proposer_name} offers`,
                tradeToView.offer_money,
                tradeToView.offer_properties,
                tradeToView.offer_lobby_pledges,
                'text-green-400'
              )}
              {renderTradeCard(
                `${tradeToView.proposer_name} requests`,
                tradeToView.request_money,
                tradeToView.request_properties,
                tradeToView.request_lobby_pledges,
                'text-red-400'
              )}
            </div>
            {(tradeToView.included_deal_drafts || []).length > 0 && (
              <div className="bg-gray-800 rounded-xl p-4 space-y-3">
                <h3 className="text-sm font-semibold text-cyan-300">Attached Deal Drafts</h3>
                <div className="space-y-3">
                  {tradeToView.included_deal_drafts.map((draft, index) => (
                    <div key={`trade-draft-${index}`} className="rounded-lg border border-cyan-900/40 bg-gray-900/80 p-3">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-semibold text-white">{draft.title || `Deal Draft ${index + 1}`}</p>
                        <span className="text-xs text-cyan-200">{draft.clauses?.length || 0} clauses</span>
                      </div>
                      <div className="mt-3 space-y-2">
                        {(draft.clauses || []).map((clause, clauseIndex) => (
                          <div key={`trade-draft-${index}-clause-${clauseIndex}`} className="rounded-lg border border-gray-700 bg-gray-950/70 px-3 py-2">
                            <div className="flex items-center justify-between gap-3">
                              <span className="text-xs font-semibold uppercase tracking-[0.18em] text-gray-400">Clause {clauseIndex + 1}</span>
                              <span className="text-xs text-gray-500">{formatDealDeadline(clause.deadline)}</span>
                            </div>
                            <p className="mt-2 text-sm text-gray-300">{summarizeClause(clause, myPlayerId, players, properties, economy)}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {isReceiver && (
              <div className="flex gap-3 mt-4">
                <button
                  onClick={() => onRespond(tradeToView.id, true)}
                  className="flex-1 py-3 bg-green-600 hover:bg-green-500 text-white font-bold rounded-xl transition"
                >
                  Accept Trade
                </button>
                <button
                  onClick={() => onRespond(tradeToView.id, false)}
                  className="flex-1 py-3 bg-red-700 hover:bg-red-600 text-white font-bold rounded-xl transition"
                >
                  Decline Trade
                </button>
              </div>
            )}
          </div>
        ) : (
          /* Propose trade view */
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* Target player selector */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Trade with:</label>
              <div className="flex gap-2 flex-wrap">
                {others.map((p) => {
                  const textColor = needsDarkText(p.color_hex) ? '#111' : '#fff';
                  return (
                    <button
                      key={p.id}
                      onClick={() => setTargetPlayerId(p.id)}
                      className={[
                        'flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm font-medium transition',
                        targetPlayerId === p.id
                          ? 'border-blue-500 bg-blue-900/40'
                          : 'border-gray-600 bg-gray-800 hover:border-gray-400',
                      ].join(' ')}
                    >
                      <div
                        className="w-4 h-4 rounded-full"
                        style={{ backgroundColor: p.color_hex || '#888' }}
                      />
                      <span className="text-gray-200">{p.username}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Split: your offer | your request */}
            <div className="grid grid-cols-2 gap-4">
              {/* Your offer */}
              <div className="bg-gray-800 rounded-xl p-4 space-y-3">
                <h3 className="text-sm font-semibold text-green-400">Your Offer</h3>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Money ($)</label>
                  <input
                    type="number"
                    min={0}
                    max={availableOfferBalance}
                    value={offerMoney}
                    onChange={(e) => setOfferMoney(Math.max(0, Number(e.target.value)))}
                    className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-white text-sm
                               focus:outline-none focus:border-green-500"
                  />
                  <p className="text-xs text-gray-600 mt-0.5">Balance: {formatMoney(me?.balance)}</p>
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Your Properties</label>
                  <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto">
                    {myProperties.length === 0 && (
                      <p className="text-xs text-gray-600 italic">No properties</p>
                    )}
                    {myProperties.map((pos) => (
                      <PropertyChip
                        key={pos}
                        position={pos}
                        selected={offerProperties.includes(pos)}
                        onAdd={addOffer}
                        onRemove={removeOffer}
                      />
                    ))}
                  </div>
                </div>
                {canPledgeLobbying && policyOptions.length > 0 && (
                  <div className="rounded-lg border border-gray-700 bg-gray-900/70 p-3 space-y-2">
                    <label className="text-xs text-gray-500 block">Lobby Pledge</label>
                    <select
                      value={offerLobbyTarget}
                      onChange={(e) => setOfferLobbyTarget(e.target.value)}
                      className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-white text-sm focus:outline-none focus:border-fuchsia-500"
                    >
                      <option value="">No lobbying pledge</option>
                      {policyOptions.map((option) => (
                        <option key={option.target} value={option.target}>{option.label}</option>
                      ))}
                    </select>
                    <input
                      type="number"
                      min={0}
                      step={25}
                      value={offerLobbyAmount}
                      onChange={(e) => setOfferLobbyAmount(Math.max(0, Number(e.target.value) || 0))}
                      className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-white text-sm focus:outline-none focus:border-fuchsia-500"
                      placeholder="Pledged contribution"
                    />
                    <p className="text-[11px] leading-4 text-gray-500">If the trade is accepted, this amount is spent immediately into the chosen lobbying pool.</p>
                  </div>
                )}
              </div>

              {/* Your request */}
              <div className="bg-gray-800 rounded-xl p-4 space-y-3">
                <h3 className="text-sm font-semibold text-red-400">You Want</h3>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Money ($)</label>
                  <input
                    type="number"
                    min={0}
                    value={requestMoney}
                    onChange={(e) => setRequestMoney(Math.max(0, Number(e.target.value)))}
                    className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-white text-sm
                               focus:outline-none focus:border-red-500"
                  />
                  {target && (
                    <p className="text-xs text-gray-600 mt-0.5">
                      Their balance: {formatMoney(target.balance)}
                    </p>
                  )}
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Their Properties</label>
                  <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto">
                    {!targetPlayerId && (
                      <p className="text-xs text-gray-600 italic">Select a player first</p>
                    )}
                    {targetPlayerId && targetProperties.length === 0 && (
                      <p className="text-xs text-gray-600 italic">No properties</p>
                    )}
                    {targetProperties.map((pos) => (
                      <PropertyChip
                        key={pos}
                        position={pos}
                        selected={requestProperties.includes(pos)}
                        onAdd={addRequest}
                        onRemove={removeRequest}
                      />
                    ))}
                  </div>
                </div>
                {canPledgeLobbying && policyOptions.length > 0 && (
                  <div className="rounded-lg border border-gray-700 bg-gray-900/70 p-3 space-y-2">
                    <label className="text-xs text-gray-500 block">Their Lobby Pledge</label>
                    <select
                      value={requestLobbyTarget}
                      onChange={(e) => setRequestLobbyTarget(e.target.value)}
                      className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-white text-sm focus:outline-none focus:border-fuchsia-500"
                    >
                      <option value="">No lobbying pledge</option>
                      {policyOptions.map((option) => (
                        <option key={option.target} value={option.target}>{option.label}</option>
                      ))}
                    </select>
                    <input
                      type="number"
                      min={0}
                      step={25}
                      value={requestLobbyAmount}
                      onChange={(e) => setRequestLobbyAmount(Math.max(0, Number(e.target.value) || 0))}
                      className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-white text-sm focus:outline-none focus:border-fuchsia-500"
                      placeholder="Requested contribution"
                    />
                    <p className="text-[11px] leading-4 text-gray-500">Use this when you want the other player to fund a policy push as part of the deal.</p>
                  </div>
                )}
              </div>
            </div>

            <div className="bg-gray-800 rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold text-cyan-300">Bundled Deal Drafts</h3>
                  <p className="mt-1 text-xs text-gray-500">Save a draft from the Deals Desk, then attach it here so the trade can activate the contract immediately on acceptance.</p>
                </div>
                <span className="text-xs text-gray-500">{selectedDraftIds.length} selected</span>
              </div>

              {!targetPlayerId && visibleDealDrafts.length > 0 && (
                <p className="text-xs text-gray-500 italic">Pick a saved draft below to lock the trade partner automatically, or choose a player first.</p>
              )}

              {!targetPlayerId && visibleDealDrafts.length === 0 && (
                <p className="text-xs text-gray-500 italic">No saved deal drafts yet.</p>
              )}

              {targetPlayerId && availableDealDrafts.length === 0 && (
                <p className="text-xs text-gray-500 italic">No saved deal drafts for this player yet.</p>
              )}

              <div className="space-y-2">
                {visibleDealDrafts.map((draft) => {
                  const isSelected = selectedDraftIds.includes(draft.id);
                  const draftCounterparty = players.find((player) => player.id === Number(draft.counterparty_id || 0));
                  return (
                    <div
                      key={draft.id}
                      className={[
                        'flex items-start justify-between gap-3 rounded-xl border p-3',
                        isSelected ? 'border-cyan-500 bg-cyan-950/20' : 'border-gray-700 bg-gray-900/80',
                      ].join(' ')}
                    >
                      <button
                        type="button"
                        onClick={() => selectDealDraft(draft)}
                        aria-pressed={isSelected}
                        className="flex-1 text-left"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-sm font-semibold text-white">{draft.title || 'Untitled deal draft'}</p>
                          <span className="text-xs text-gray-400">{draft.clauses?.length || 0} clauses</span>
                        </div>
                        {!targetPlayerId && draftCounterparty && (
                          <p className="mt-2 text-[11px] uppercase tracking-[0.18em] text-cyan-300/80">
                            Attach with {draftCounterparty.username}
                          </p>
                        )}
                        {(draft.clauses || []).slice(0, 2).map((clause, index) => (
                          <p key={`${draft.id}-preview-${index}`} className="mt-2 text-xs leading-5 text-gray-300">
                            {summarizeClause(clause, myPlayerId, players, properties, economy)}
                          </p>
                        ))}
                      </button>
                      <button
                        type="button"
                        onClick={() => deleteTradeDealDraft(draft.id)}
                        className="rounded-lg border border-rose-800/60 px-2.5 py-1 text-xs font-semibold text-rose-200 transition hover:border-rose-500 hover:text-white"
                      >
                        Remove
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>

            {error && (
              <p className="text-red-400 text-sm text-center">{error}</p>
            )}

            <button
              onClick={handleSubmit}
              disabled={!targetPlayerId}
              className="w-full py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700
                         disabled:cursor-not-allowed text-white font-bold rounded-xl transition"
            >
              Propose Trade
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
