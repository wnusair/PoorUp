import { useEffect, useRef, useCallback } from 'react';
import { io } from 'socket.io-client';
import { useGameStore } from './useGameState';
import {
  normalizeDeal,
  normalizeDeals,
  normalizeEconomy,
  normalizePendingDebts,
  normalizeProperties,
  normalizePlayers,
  normalizeSettings,
  normalizeSocial,
} from '../utils/gameState';
import { BOARD_POSITION_ORDER } from '../utils/constants';

const SOCKET_SERVER_URL = import.meta.env.VITE_SOCKET_URL?.trim() || undefined;
const SOCKET_PATH = import.meta.env.VITE_SOCKET_PATH?.trim() || '/socket.io';
const DISCONNECT_GRACE_PERIOD_MS = 750;
const SOCKET_ACK_TIMEOUT_MS = 5000;
const BOARD_INDEX_BY_POSITION = Object.fromEntries(BOARD_POSITION_ORDER.map((position, index) => [position, index]));

function normalizeBoardPosition(position) {
  if (BOARD_INDEX_BY_POSITION[position] != null) {
    return position;
  }

  for (const candidate of BOARD_POSITION_ORDER) {
    if (candidate >= Number(position || 0)) {
      return candidate;
    }
  }

  return BOARD_POSITION_ORDER[0] ?? 0;
}

function buildBoardWalk(fromPosition, toPosition) {
  const normalizedFrom = normalizeBoardPosition(fromPosition);
  const normalizedTo = normalizeBoardPosition(toPosition);

  if (normalizedFrom === normalizedTo) {
    return [];
  }

  const steps = [];
  let cursor = BOARD_INDEX_BY_POSITION[normalizedFrom];
  const targetIndex = BOARD_INDEX_BY_POSITION[normalizedTo];

  while (cursor !== targetIndex) {
    cursor = (cursor + 1) % BOARD_POSITION_ORDER.length;
    steps.push(BOARD_POSITION_ORDER[cursor]);
  }

  return steps;
}

let socketInstance = null;
let socketUsageCount = 0;
let disconnectTimeoutId = null;

function buildSocketAuth({ playerId, roomCode }) {
  return {
    token: localStorage.getItem('poorup_token'),
    playerId,
    roomCode,
  };
}

function getOrCreateSocket(auth) {
  if (disconnectTimeoutId) {
    clearTimeout(disconnectTimeoutId);
    disconnectTimeoutId = null;
  }

  if (!socketInstance) {
    socketInstance = io(SOCKET_SERVER_URL, {
      path: SOCKET_PATH,
      auth,
      transports: ['websocket', 'polling'],
      withCredentials: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
    });
  } else {
    socketInstance.auth = auth;
    if (!socketInstance.connected && !socketInstance.active) {
      socketInstance.connect();
    }
  }

  socketUsageCount += 1;
  return socketInstance;
}

function releaseSocket() {
  socketUsageCount = Math.max(0, socketUsageCount - 1);

  if (socketUsageCount > 0 || !socketInstance || disconnectTimeoutId) {
    return;
  }

  disconnectTimeoutId = window.setTimeout(() => {
    if (socketUsageCount === 0 && socketInstance) {
      socketInstance.disconnect();
      socketInstance = null;
    }
    disconnectTimeoutId = null;
  }, DISCONNECT_GRACE_PERIOD_MS);
}

function emitJoinRoom(socket, roomCode, matchId) {
  if (!roomCode && !matchId) {
    return;
  }

  socket.emit('join_room', {
    ...(roomCode ? { room_code: roomCode } : {}),
    ...(matchId ? { match_id: matchId } : {}),
  });
}

function emitLeaveRoom(socket, roomCode, matchId) {
  if ((!roomCode && !matchId) || !socket.connected) {
    return;
  }

  socket.emit('leave_room', {
    ...(roomCode ? { room_code: roomCode } : {}),
    ...(matchId ? { match_id: matchId } : {}),
  });
}

function normalizeCardDrawPayload(data) {
  const state = useGameStore.getState();
  const players = state.players || [];
  const card = data?.card || null;
  const player = players.find((candidate) => candidate.id === data?.player_id);
  const cardType = data?.card_type || data?.type || card?.deck_type || 'chance';

  return {
    ...data,
    card,
    card_type: cardType,
    card_text: data?.card_text || card?.card_text || 'Unknown card',
    player_name: data?.player_name || player?.username || 'Player',
  };
}

function normalizeTradePayload(data) {
  const state = useGameStore.getState();
  const players = state.players || [];
  const properties = state.properties || {};
  const trade = data?.trade ?? data ?? {};
  const proposerId = trade.proposer_id ?? trade.initiator_id ?? null;
  const receiverId = trade.receiver_id ?? null;
  const proposer = players.find((player) => player.id === proposerId);
  const receiver = players.find((player) => player.id === receiverId);

  const toBoardPositions = (refs = []) => refs
    .map((ref) => {
      if (properties[ref]?.position != null) {
        return properties[ref].position;
      }

      const property = Object.values(properties).find((candidate) => candidate.id === ref);
      return property?.position ?? property?.board_position ?? null;
    })
    .filter((position) => position != null);

  const normalizeLobbyPledges = (pledges = []) => (Array.isArray(pledges) ? pledges : [])
    .map((pledge) => ({
      policy_id: pledge?.policy_id ?? null,
      target: pledge?.target || pledge?.target_stat || '',
      policy_name: pledge?.policy_name || pledge?.target || 'Policy',
      amount: Number(pledge?.amount ?? pledge?.contribution ?? 0) || 0,
    }))
    .filter((pledge) => pledge.amount > 0);

  return {
    ...trade,
    proposer_id: proposerId,
    receiver_id: receiverId,
    proposer_name: trade.proposer_name ?? trade.initiator_username ?? proposer?.username ?? 'Player',
    receiver_name: trade.receiver_name ?? trade.receiver_username ?? receiver?.username ?? 'Player',
    offer_money: trade.offer_money ?? trade.offered_money ?? 0,
    request_money: trade.request_money ?? trade.requested_money ?? 0,
    offer_properties: toBoardPositions(trade.offer_properties ?? trade.offered_props ?? []),
    request_properties: toBoardPositions(trade.request_properties ?? trade.requested_props ?? []),
    offer_lobby_pledges: normalizeLobbyPledges(trade.offer_lobby_pledges ?? trade.offered_lobby_pledges ?? []),
    request_lobby_pledges: normalizeLobbyPledges(trade.request_lobby_pledges ?? trade.requested_lobby_pledges ?? []),
    included_deal_drafts: Array.isArray(trade.included_deal_drafts)
      ? trade.included_deal_drafts.map((draft) => normalizeDeal(draft))
      : [],
  };
}


function normalizeDealPayload(data) {
  return normalizeDeal(data?.deal ?? data ?? {});
}

function normalizeLogEntry(entry) {
  return {
    ...entry,
    type: entry?.type || entry?.event_type || 'move',
    message: entry?.message || entry?.description || '',
    timestamp: entry?.timestamp || new Date().toISOString(),
  };
}

function humanizeToken(value) {
  return String(value || '')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatCurrency(value) {
  const amount = Number(value) || 0;
  return `$${amount.toFixed(2)}`;
}

function incidentSubject(data) {
  if (data?.property_name) {
    return data.property_name;
  }
  if (data?.property_id != null) {
    return `property #${data.property_id}`;
  }
  return 'an affected property';
}

function incidentLogDescription(data, verb = 'started on') {
  const incidentType = humanizeToken(data?.incident_type || 'incident');
  const subject = incidentSubject(data);
  const grievance = data?.dominant_grievance ? ` Dominant grievance: ${humanizeToken(data.dominant_grievance)}.` : '';
  const negotiation = Number(data?.negotiation_target) > 0
    ? ` Negotiation ${formatCurrency(data?.negotiation_committed)} / ${formatCurrency(data?.negotiation_target)}.`
    : '';
  const reintegration = Number(data?.reintegration_progress) > 0
    ? ` Reintegration ${Math.round(Number(data.reintegration_progress) || 0)}%.`
    : '';
  const spread = data?.spread_block_active ? ' Spread blocked this round.' : '';
  return `${incidentType} ${verb} ${subject}${data?.region ? ` in ${data.region}` : ''}.${grievance}${negotiation}${reintegration}${spread}`;
}

function buildUnrestOverlayEvent(data, fallbackType = 'uprising') {
  const incidentType = data?.incident_type || fallbackType;
  const seizedProperties = Array.isArray(data?.seized_properties)
    ? data.seized_properties.map((entry) => entry?.property_name || `Property #${entry?.property_id}`)
    : [];
  return {
    event_type: data?.event_type || 'structured_unrest',
    incident_type: incidentType,
    region: data?.region,
    property_name: data?.property_name || null,
    description: incidentType === 'revolution'
      ? `Union control spread through ${data?.region || 'the territory'}.`
      : `${humanizeToken(incidentType)} pressure broke out on ${incidentSubject(data)}.`,
    affected_properties: seizedProperties,
  };
}

function applyGameStateSnapshot(gameState, actions) {
  if (!gameState) return;

  const normalizedSocial = normalizeSocial(gameState.social, gameState);

  actions.setSocial(normalizedSocial);
  actions.setDeals(normalizeDeals(gameState.deals || []));

  if (gameState.players) {
    actions.setPlayers(normalizePlayers(gameState.players));
  }

  actions.setPendingDebts(normalizePendingDebts(gameState.pending_debts || []));

  if (gameState.properties) {
    actions.setProperties(normalizeProperties(gameState.properties, normalizedSocial.properties));
  }

  if (gameState.econ) {
    actions.setEconomy(normalizeEconomy(gameState.econ, gameState));
  }

  if (gameState.tax_stats) {
    actions.setTaxStats(gameState.tax_stats);
  }

  if (gameState.lobbying_stats) {
    actions.setLobbyingStats(gameState.lobbying_stats);
  }

  if (gameState.player_finance_history) {
    actions.setPlayerFinanceHistory(gameState.player_finance_history);
  }

  if (gameState.settings) {
    actions.setSettings(normalizeSettings(gameState.settings));
  }

  actions.setAwaitingEndTurnPlayerId(gameState.awaiting_end_turn_player_id ?? null);

  if (gameState.current_player_id != null) {
    actions.setCurrentPlayerId(gameState.current_player_id);
  }

  if (gameState.dice_rolled_this_turn != null) {
    actions.setDiceRolledThisTurn(Boolean(gameState.dice_rolled_this_turn));
    if (!gameState.dice_rolled_this_turn) {
      actions.setDiceResult(null);
      actions.setIsRolling(false);
    }
  }

  if (gameState.pending_action) {
    const pendingType = gameState.pending_action.type || 'buy_property';
    const myPlayerId = useGameStore.getState().myPlayerId;
    const isMovementInProgress = useGameStore.getState().movingPlayerId !== null;
    const isLocalPrompt = gameState.pending_action.player_id == null || gameState.pending_action.player_id === myPlayerId;

    if (isLocalPrompt) {
      actions.setPendingAction({ type: pendingType, data: gameState.pending_action });
    } else {
      const state = useGameStore.getState();
      if (state.pendingAction?.type === 'buy_property') {
        if (state.activeModal === 'property') {
          actions.closeModal();
        }
        actions.clearPendingAction();
      }
    }
    if (isLocalPrompt && pendingType === 'buy_property') {
      if (isMovementInProgress) {
        useGameStore.getState().queuePendingEvent(() => {
          const state = useGameStore.getState();
          state.setPendingAction({ type: pendingType, data: gameState.pending_action });
          state.setActiveModal('property');
        });
      } else {
        actions.setActiveModal('property');
      }
    }
  } else {
    const state = useGameStore.getState();
    if (state.pendingAction?.type === 'buy_property') {
      if (state.activeModal === 'property') {
        actions.closeModal();
      }
      actions.clearPendingAction();
    }
  }
}

export function getSocket() {
  return socketInstance;
}

export function useSocket({ roomCode, matchId = null, playerId, enabled = true } = {}) {
  const socketRef = useRef(null);

  const {
    setPlayers,
    setPendingDebts,
    updatePlayer,
    setCurrentPlayerId,
    setProperties,
    updateProperty,
    setEconomy,
    setTaxStats,
    setLobbyingStats,
    setPlayerFinanceHistory,
    setSocial,
    updateEconomy,
    addLogEntry,
    setLogEntries,
    setPendingAction,
    clearPendingAction,
    setActiveModal,
    closeModal,
    setDiceResult,
    setDiceRolledThisTurn,
    setIsRolling,
    setDiceRollTime,
    setPlayerAnimPos,
    clearPlayerAnimPos,
    setMovingPlayerId,
    queuePendingEvent,
    flushPendingEvents,
    setUprisingEvent,
    setHyperInflation,
    setAuctionState,
    updateAuction,
    clearAuction,
    setTrades,
    upsertTrade,
    removeTrade,
    setActiveTrade,
    setDeals,
    upsertDeal,
    setActiveDeal,
    clearActiveDeal,
    enqueueModal,
    removeQueuedModal,
    setAwaitingEndTurnPlayerId,
    setLobbyData,
    setSettings,
    setTakenColors,
    addTakenColor,
    setGamePhase,
    setMatchId,
  } = useGameStore.getState();

  // Run fn immediately if no movement animation is in progress; otherwise queue it.
  const queueOrRun = (fn) => {
    if (useGameStore.getState().movingPlayerId !== null) {
      queuePendingEvent(fn);
    } else {
      fn();
    }
  };

  useEffect(() => {
    if (!enabled) return undefined;

    const socket = getOrCreateSocket(buildSocketAuth({ playerId, roomCode }));
    const listeners = [];

    const subscribe = (event, handler) => {
      socket.on(event, handler);
      listeners.push([event, handler]);
    };

    socketInstance = socket;
    socketRef.current = socket;

    // ─── Game lifecycle ───────────────────────────────────────────────
    subscribe('game_start', (data) => {
      setGamePhase('playing');
      if (data.match_id) setMatchId(data.match_id);
      if (data.first_player_id) setCurrentPlayerId(data.first_player_id);

      if (data.state) {
        applyGameStateSnapshot(data.state, {
          setPlayers,
          setPendingDebts,
          setProperties,
          setEconomy,
          setTaxStats,
          setLobbyingStats,
          setPlayerFinanceHistory,
          setSocial,
          setDeals,
          setCurrentPlayerId,
          setSettings,
          setPendingAction,
          clearPendingAction,
          setActiveModal,
          closeModal,
          setDiceResult,
          setDiceRolledThisTurn,
          setIsRolling,
          setAwaitingEndTurnPlayerId,
        });
      } else {
        if (data.players) setPlayers(normalizePlayers(data.players));
        if (data.properties) setProperties(normalizeProperties(data.properties));
        if (data.economy) setEconomy(data.economy);
        if (data.deals) setDeals(normalizeDeals(data.deals));
      }
      addLogEntry({ type: 'move', message: 'Game started!', timestamp: new Date().toISOString() });
    });

    subscribe('game_state_snapshot', (data) => {
      setGamePhase('playing');

      if (data.your_player_id != null) {
        useGameStore.getState().setMyPlayerId(data.your_player_id);
      }

      applyGameStateSnapshot(data.state, {
        setPlayers,
        setPendingDebts,
        setProperties,
        setEconomy,
        setTaxStats,
        setLobbyingStats,
        setPlayerFinanceHistory,
        setSocial,
        setDeals,
        setCurrentPlayerId,
        setSettings,
        setPendingAction,
        clearPendingAction,
        setActiveModal,
        closeModal,
        setDiceResult,
        setDiceRolledThisTurn,
        setIsRolling,
        setAwaitingEndTurnPlayerId,
      });
    });

    subscribe('turn_start', (data) => {
      setCurrentPlayerId(data.player_id);
      const state = useGameStore.getState();
      useGameStore.setState({
        diceResult: null,
        diceRolledThisTurn: false,
        isRolling: false,
        awaitingEndTurnPlayerId: null,
        pendingAction: null,
        activeModal:
          state.activeModal === 'property' && state.pendingAction?.type === 'buy_property'
            ? null
            : state.activeModal,
      });
      addLogEntry({
        type: 'move',
        message: `${data.player_name || 'Player'}'s turn`,
        player_id: data.player_id,
        timestamp: new Date().toISOString(),
      });
    });

    // ─── Dice ─────────────────────────────────────────────────────────
    subscribe('dice_rolled', (data) => {
      setDiceRollTime(Date.now());
      setDiceRolledThisTurn(true);
      setIsRolling(true);
      setTimeout(() => {
        setDiceResult({ die1: data.die1, die2: data.die2, total: data.total });
        setIsRolling(false);
      }, 600);
      addLogEntry({
        type: 'dice_roll',
        message: `${data.player_name || 'Player'} rolled ${data.die1} + ${data.die2} = ${data.total}`,
        player_id: data.player_id,
        timestamp: new Date().toISOString(),
      });
    });

    // ─── Movement ─────────────────────────────────────────────────────
    subscribe('player_moved', (data) => {
      const STEP_MS = 160;      // ms between each board space step
      const DICE_ANIM_MS = 650; // how long the dice animation runs
      const MAX_WALK_STEPS = 12; // beyond this we treat as teleport

      const pos = normalizeBoardPosition(data.position ?? data.to);
      const state = useGameStore.getState();
      const player = state.players.find((p) => p.id === data.player_id);
      const fromPos = normalizeBoardPosition(state.playerAnimPositions[data.player_id] ?? player?.position ?? 0);

      const steps = buildBoardWalk(fromPos, pos);

      // Delay movement until the dice animation has finished
      const diceDelay = Math.max(0, DICE_ANIM_MS - (Date.now() - (state.diceRollTime || 0)));

      const finishMovement = () => {
        const latestState = useGameStore.getState();
        const latestPlayer = latestState.players.find((entry) => entry.id === data.player_id);
        const finalPosition = latestPlayer?.position != null && latestPlayer.position !== fromPos
          ? latestPlayer.position
          : pos;

        updatePlayer(data.player_id, { position: finalPosition });
        clearPlayerAnimPos(data.player_id);
        setMovingPlayerId(null);
        flushPendingEvents();
      };

      if (steps.length === 0 || steps.length > MAX_WALK_STEPS) {
        // Teleport (go to jail, advance to GO, etc.) — quick flash
        setMovingPlayerId(data.player_id);
        setPlayerAnimPos(data.player_id, pos);
        setTimeout(() => {
          finishMovement();
        }, diceDelay + 400);
      } else {
        // Step-by-step walk animation
        setMovingPlayerId(data.player_id);
        steps.forEach((stepPos, i) => {
          setTimeout(() => {
            setPlayerAnimPos(data.player_id, stepPos);
            if (i === steps.length - 1) {
              // Small pause on landing space before unlocking events
              setTimeout(() => finishMovement(), 250);
            }
          }, diceDelay + (i + 1) * STEP_MS);
        });
      }

      addLogEntry({
        type: 'move',
        message: `${data.player_name || 'Player'} moved to ${data.space_name || `space ${pos}`}`,
        player_id: data.player_id,
        timestamp: new Date().toISOString(),
      });
    });

    // ─── Rent ─────────────────────────────────────────────────────────
    subscribe('rent_collected', (data) => {
      queueOrRun(() => {
        const state = useGameStore.getState();
        const payer = state.players.find((player) => player.id === data.payer_id);
        const owner = state.players.find((player) => player.id === data.owner_id);

        if (data.payer_balance != null) {
          updatePlayer(data.payer_id, { balance: data.payer_balance });
        }
        if (data.owner_balance != null) {
          updatePlayer(data.owner_id, { balance: data.owner_balance });
        }

        const totalRent = data.total_rent ?? data.amount ?? 0;
        const amountPaid = data.amount_paid ?? data.amount ?? 0;
        const amountDue = data.amount_due ?? 0;
        const rentMessage = amountDue > 0
          ? `${data.payer_name || payer?.username || 'Player'} paid $${amountPaid} toward $${totalRent} rent to ${data.owner_name || owner?.username || 'Player'}. $${amountDue} is still owed.`
          : `${data.payer_name || payer?.username || 'Player'} paid $${totalRent} rent to ${data.owner_name || owner?.username || 'Player'}`;

        addLogEntry({
          type: 'rent_collected',
          message: rentMessage,
          player_id: data.payer_id,
          timestamp: new Date().toISOString(),
        });
      });
    });

    // ─── Property ─────────────────────────────────────────────────────
    subscribe('property_purchased', (data) => {
      queueOrRun(() => {
        const state = useGameStore.getState();
        const propertyPosition = data.position ?? Object.values(state.properties).find((property) => property.id === data.property_id)?.board_position;
        const player = state.players.find((entry) => entry.id === data.player_id);
        const purchasePrice = data.price ?? (propertyPosition != null ? state.properties[propertyPosition]?.current_value : 0) ?? 0;

        if (data.player_balance != null) {
          updatePlayer(data.player_id, { balance: data.player_balance });
        }
        if (propertyPosition != null) {
          updateProperty(propertyPosition, {
            owner_id: data.player_id,
            current_value: purchasePrice,
          });
        }

        addLogEntry({
          type: 'property_purchased',
          message: `${data.player_name || player?.username || 'Player'} bought ${data.property_name || 'a property'} for $${purchasePrice}`,
          player_id: data.player_id,
          timestamp: new Date().toISOString(),
        });
      });
    });

    // ─── Auction ─────────────────────────────────────────────────────
    subscribe('auction_start', (data) => {
      queueOrRun(() => {
        const state = useGameStore.getState();
        const property = data.property
          || (data.position != null ? state.properties[data.position] : null)
          || Object.values(state.properties).find((entry) => entry.id === data.property_id)
          || null;
        setAuctionState({
          property,
          position: data.position,
          bids: [],
          highestBid: data.starting_bid || 0,
          highestBidderId: null,
          timeLeft: data.countdown_seconds || 5,
          active: true,
        });
        setActiveModal('auction');
      });
    });

    subscribe('auction_bid', (data) => {
      updateAuction({
        bids: [...(useGameStore.getState().auctionState?.bids || []), data],
        highestBid: data.amount,
        highestBidderId: data.player_id,
        timeLeft: data.countdown_seconds || 5,
      });
    });

    subscribe('auction_end', (data) => {
      const state = useGameStore.getState();
      const propertyPosition = data.position ?? Object.values(state.properties).find((property) => property.id === data.property_id)?.board_position;
      if (data.winner_id) {
        if (data.winner_balance != null) {
          updatePlayer(data.winner_id, { balance: data.winner_balance });
        }
        if (propertyPosition != null) {
          updateProperty(propertyPosition, { owner_id: data.winner_id });
        }
        addLogEntry({
          type: 'auction_won',
          message: `${data.winner_name || 'Player'} won auction for ${data.property_name || 'a property'} at $${data.amount}`,
          player_id: data.winner_id,
          timestamp: new Date().toISOString(),
        });
      }
      setTimeout(() => {
        clearAuction();
        const latestState = useGameStore.getState();
        if (latestState.activeModal === 'auction') {
          latestState.closeModal();
        }
      }, 2000);
    });

    // ─── Trade ─────────────────────────────────────────────────────────
    subscribe('trade_proposed', (data) => {
      const trade = normalizeTradePayload(data);
      upsertTrade(trade);
      queueOrRun(() => {
        const state = useGameStore.getState();
        const shouldOpenImmediately = trade.receiver_id === state.myPlayerId && !state.auctionState?.active && !state.activeModal;
        if (shouldOpenImmediately) {
          setActiveTrade(trade);
          setActiveModal('trade');
          return;
        }

        if (trade.receiver_id === state.myPlayerId) {
          enqueueModal('trade', trade.id);
        }
      });
      addLogEntry({
        type: 'trade_proposed',
        message: `${trade.proposer_name} proposed a trade to ${trade.receiver_name}`,
        player_id: trade.proposer_id,
        timestamp: new Date().toISOString(),
      });
    });

    subscribe('trade_resolved', (data) => {
      const trade = normalizeTradePayload(data);
      const stateBeforeResolution = useGameStore.getState();
      const isActiveTrade = stateBeforeResolution.activeTrade?.id === trade.id;

      if (data.accepted) {
        addLogEntry({
          type: 'trade_completed',
          message: `Trade completed between ${trade.proposer_name} and ${trade.receiver_name}`,
          player_id: trade.proposer_id,
          timestamp: new Date().toISOString(),
        });
        // update balances and properties
        if (data.players) data.players.forEach((p) => updatePlayer(p.id, p));
        if (data.properties)
          data.properties.forEach((prop) => updateProperty(prop.position, prop));
        if (Array.isArray(data.created_deals)) {
          data.created_deals
            .map((deal) => normalizeDealPayload(deal))
            .forEach((deal) => upsertDeal(deal));
        }
      } else {
        addLogEntry({
          type: 'trade_rejected',
          message: `Trade between ${trade.proposer_name} and ${trade.receiver_name} was rejected`,
          player_id: trade.proposer_id,
          timestamp: new Date().toISOString(),
        });
      }
      removeTrade(trade.id);
      if (isActiveTrade && useGameStore.getState().activeModal === 'trade') {
        useGameStore.getState().closeModal();
      }
    });

    // ─── Cards ─────────────────────────────────────────────────────────
    subscribe('card_drawn', (data) => {
      const normalizedData = normalizeCardDrawPayload(data);
      queueOrRun(() => {
        addLogEntry({
          type: normalizedData.card_type === 'chance' ? 'chance_card' : 'community_chest',
          message: `${normalizedData.player_name} drew: ${normalizedData.card_text}`,
          player_id: normalizedData.player_id,
          timestamp: new Date().toISOString(),
        });

        const state = useGameStore.getState();
        if (state.pendingAction?.type === 'buy_property') {
          return;
        }

        setPendingAction({ type: 'card_drawn', data: normalizedData });
        setActiveModal('card');
      });
    });

    // ─── Log ──────────────────────────────────────────────────────────
    subscribe('log_entry', (data) => {
      const entries = Array.isArray(data?.log) ? data.log : [data];
      entries
        .filter(Boolean)
        .map(normalizeLogEntry)
        .forEach((entry) => addLogEntry(entry));
    });

    // ─── Economy ──────────────────────────────────────────────────────
    subscribe('economy_update', (data) => {
      const storeState = useGameStore.getState();
      const currentEconomy = storeState.economy || {};
      if (data?.econ) {
        setEconomy(normalizeEconomy({ ...currentEconomy, ...data.econ }, storeState));
        return;
      }
      setEconomy(normalizeEconomy({ ...currentEconomy, ...data }, storeState));
    });

    subscribe('stability_update', (data) => {
      const storeState = useGameStore.getState();
      const normalizedSocial = normalizeSocial(data?.social, storeState);
      setSocial(normalizedSocial);
      setProperties(normalizeProperties(storeState.properties, normalizedSocial.properties));
      updateEconomy({ rage: normalizedSocial.overall_rage });
    });

    subscribe('lobby_success', (data) => {
      addLogEntry(normalizeLogEntry({
        event_type: 'lobby_success',
        description: data?.effect_summary
          ? `Lobbying succeeded: ${data.effect_summary}`
          : data?.policy_name
          ? `Lobbying succeeded: ${data.policy_name}`
          : 'A lobbying effort succeeded.',
      }));
    });

    subscribe('lobby_failed', (data) => {
      addLogEntry(normalizeLogEntry({
        event_type: 'lobby_failed',
        description: data?.reason || 'A lobbying effort failed.',
      }));
    });

    subscribe('revolt_started', (data) => {
      addLogEntry(normalizeLogEntry({
        event_type: 'revolt_started',
        description: incidentLogDescription(data, 'started on'),
      }));
      if (data?.incident_type === 'uprising') {
        queueOrRun(() => setUprisingEvent(buildUnrestOverlayEvent(data, 'uprising')));
      }
    });

    subscribe('revolt_updated', (data) => {
      addLogEntry(normalizeLogEntry({
        event_type: 'revolt_updated',
        description: incidentLogDescription(data, 'continues on'),
      }));
      if (data?.incident_type === 'uprising') {
        queueOrRun(() => setUprisingEvent(buildUnrestOverlayEvent(data, 'uprising')));
      }
    });

    subscribe('revolt_resolved', (data) => {
      addLogEntry(normalizeLogEntry({
        event_type: 'revolt_resolved',
        description: `${humanizeToken(data?.incident_type || 'incident')} resolved on ${incidentSubject(data)}${data?.region ? ` in ${data.region}` : ''}.`,
      }));
    });

    subscribe('revolution_started', (data) => {
      addLogEntry(normalizeLogEntry({
        event_type: 'revolution_started',
        description: `${incidentLogDescription({ ...data, incident_type: 'revolution' }, 'began in')} ${Array.isArray(data?.seized_properties) && data.seized_properties.length > 0 ? `Seized: ${data.seized_properties.map((entry) => entry.property_name || `Property #${entry.property_id}`).join(', ')}.` : ''}`,
      }));
      queueOrRun(() => setUprisingEvent(buildUnrestOverlayEvent({ ...data, incident_type: 'revolution' }, 'revolution')));
    });

    subscribe('union_property_joined', (data) => {
      addLogEntry(normalizeLogEntry({
        event_type: 'union_property_joined',
        description: `${incidentSubject(data)} joined the Proletariat Union${data?.region ? ` in ${data.region}` : ''}. Reintegration ${Math.round(Number(data?.reintegration_progress) || 0)}%.`,
      }));
    });

    subscribe('union_property_left', (data) => {
      addLogEntry(normalizeLogEntry({
        event_type: 'union_property_left',
        description: `${incidentSubject(data)} reintegrated into private ownership${data?.region ? ` in ${data.region}` : ''}.`,
      }));
    });

    subscribe('negotiation_updated', (data) => {
      addLogEntry(normalizeLogEntry({
        event_type: 'negotiation_updated',
        description: `Negotiation funding increased on property #${data?.property_id}.`,
      }));
    });

    subscribe('emergency_reform_applied', (data) => {
      addLogEntry(normalizeLogEntry({
        event_type: 'emergency_reform',
        description: `Emergency reform applied: ${data?.effect?.reform_type || 'unknown reform'}.`,
      }));
    });

    // ─── Hyper Inflation ──────────────────────────────────────────────
    subscribe('hyper_inflation_alert', (data) => {
      setHyperInflation(data);
      addLogEntry({
        type: 'hyper_inflation',
        message: `HYPER-INFLATION! Rate: ${(data.inflation_rate * 100).toFixed(1)}%`,
        timestamp: new Date().toISOString(),
      });
    });

    // ─── Deals ────────────────────────────────────────────────────────
    subscribe('deal_proposed', (data) => {
      const deal = normalizeDealPayload(data);
      upsertDeal(deal);

      const state = useGameStore.getState();
      const replacesActiveDeal = state.activeDeal?.id != null && deal.counter_of_deal_id === state.activeDeal.id;
      if (replacesActiveDeal) {
        setActiveDeal(deal);
      }

      const shouldOpenImmediately = deal.counterparty_id === state.myPlayerId && !state.activeModal;
      if (shouldOpenImmediately) {
        setActiveDeal(deal);
        setActiveModal('deals');
      } else if (deal.counterparty_id === state.myPlayerId) {
        enqueueModal('deals', deal.id);
      }

      addLogEntry(normalizeLogEntry({
        event_type: 'deal_proposed',
        description: `${deal.proposer_name || 'Player'} proposed a deal to ${deal.counterparty_name || 'another player'}.`,
      }));
    });

    subscribe('deal_updated', (data) => {
      const deal = normalizeDealPayload(data);
      upsertDeal(deal);
      if (deal.status !== 'proposed') {
        removeQueuedModal('deals', deal.id);
      }
      if (useGameStore.getState().activeDeal?.id === deal.id) {
        setActiveDeal(deal);
      }
    });

    subscribe('deal_accepted', (data) => {
      const deal = normalizeDealPayload(data);
      upsertDeal(deal);
      removeQueuedModal('deals', deal.id);
      if (useGameStore.getState().activeDeal?.id === deal.id) {
        setActiveDeal(deal);
      }
      addLogEntry(normalizeLogEntry({
        event_type: 'deal_accepted',
        description: `Deal accepted between ${deal.proposer_name || 'Player'} and ${deal.counterparty_name || 'Player'}.`,
      }));
    });

    subscribe('deal_rejected', (data) => {
      const deal = normalizeDealPayload(data);
      upsertDeal(deal);
      removeQueuedModal('deals', deal.id);
      addLogEntry(normalizeLogEntry({
        event_type: 'deal_rejected',
        description: `Deal rejected between ${deal.proposer_name || 'Player'} and ${deal.counterparty_name || 'Player'}.`,
      }));
    });

    subscribe('deal_expired', (data) => {
      const deal = normalizeDealPayload(data);
      upsertDeal(deal);
      removeQueuedModal('deals', deal.id);
      addLogEntry(normalizeLogEntry({
        event_type: 'deal_expired',
        description: `Deal expired between ${deal.proposer_name || 'Player'} and ${deal.counterparty_name || 'Player'}.`,
      }));
    });

    subscribe('deal_clause_consumed', (data) => {
      addLogEntry(normalizeLogEntry(data));
    });

    subscribe('deal_investment_spent', (data) => {
      addLogEntry(normalizeLogEntry(data));
    });

    subscribe('deal_profit_paid', (data) => {
      addLogEntry(normalizeLogEntry(data));
    });

    // ─── Bankruptcy ───────────────────────────────────────────────────
    subscribe('player_bankrupt', (data) => {
      queueOrRun(() => {
        updatePlayer(data.player_id, { bankrupt: true, balance: 0 });
        setPendingAction({ type: 'bankruptcy', data });
        setActiveModal('bankruptcy');
        addLogEntry({
          type: 'bankruptcy',
          message: `${data.player_name} is BANKRUPT!`,
          player_id: data.player_id,
          timestamp: new Date().toISOString(),
        });
      });
    });

    subscribe('player_bailed_out', (data) => {
      addLogEntry({
        type: 'welfare_paid',
        message: `${data.player_name || 'Player'} was bailed out for $${data.amount} and now has $${data.player_balance}.`,
        player_id: data.player_id,
        timestamp: new Date().toISOString(),
      });
    });

    // ─── Game over ────────────────────────────────────────────────────
    subscribe('game_over', (data) => {
      setGamePhase('ended');
      setPendingAction({ type: 'game_over', data });
      setActiveModal('game_over');
    });

    // ─── Disconnection ────────────────────────────────────────────────
    subscribe('player_disconnected', (data) => {
      updatePlayer(data.player_id, { disconnected: true });
      addLogEntry({
        type: 'move',
        message: `${data.player_name} disconnected`,
        timestamp: new Date().toISOString(),
      });
    });

    // ─── Lobby ────────────────────────────────────────────────────────
    subscribe('color_taken', (data) => {
      addTakenColor(data.color_hex || data.color);
    });

    subscribe('lobby_update', (data) => {
      setLobbyData(data);
      if (data.players) setPlayers(normalizePlayers(data.players));
      if (data.taken_colors) setTakenColors(data.taken_colors);
      if (data.settings) useGameStore.setState({ settings: normalizeSettings(data.settings) });
    });

    // ─── Property action prompts ──────────────────────────────────────
    subscribe('property_action_required', (data) => {
      queueOrRun(() => {
        const state = useGameStore.getState();
        const property = data.property
          || (data.position != null ? state.properties[data.position] : null)
          || Object.values(state.properties).find((entry) => entry.id === data.property_id)
          || null;

        if (state.myPlayerId != null && data.player_id !== state.myPlayerId) {
          return;
        }

        setPendingAction({ type: 'buy_property', data: { ...data, property } });
        setActiveModal('property');
      });
    });

    subscribe('connect', () => {
      console.log('[Socket] Connected:', socket.id);
      const activeMatchId = matchId ?? useGameStore.getState().matchId;
      emitJoinRoom(socket, roomCode, activeMatchId);
    });

    subscribe('disconnect', (reason) => {
      console.warn('[Socket] Disconnected:', reason);
    });

    subscribe('connect_error', (err) => {
      console.error('[Socket] Connection error:', err.message);
    });

    subscribe('error', (data) => {
      console.error('[Socket] Server error:', data?.message || data);
    });

    if (socket.connected) {
      emitJoinRoom(socket, roomCode, matchId ?? useGameStore.getState().matchId);
    }

    return () => {
      emitLeaveRoom(socket, roomCode, matchId ?? useGameStore.getState().matchId);
      listeners.forEach(([event, handler]) => socket.off(event, handler));
      if (socketRef.current === socket) {
        socketRef.current = null;
      }
      releaseSocket();
    };
  }, [enabled, roomCode, matchId]);

  // Emitters
  const emit = useCallback((event, data) => {
    if (socketRef.current?.connected) {
      const activeMatchId = matchId ?? useGameStore.getState().matchId;
      const payload = activeMatchId ? { ...data, match_id: activeMatchId } : data;
      socketRef.current.emit(event, payload);
    } else {
      console.warn('[Socket] Not connected, cannot emit:', event);
    }
  }, [matchId]);

  const emitWithAck = useCallback((event, data, timeoutMs = SOCKET_ACK_TIMEOUT_MS) => {
    if (!socketRef.current?.connected) {
      return Promise.reject(new Error('Not connected to the game server.'));
    }

    const activeMatchId = matchId ?? useGameStore.getState().matchId;
    const payload = activeMatchId ? { ...data, match_id: activeMatchId } : data;

    return new Promise((resolve, reject) => {
      let settled = false;
      const timerId = window.setTimeout(() => {
        if (settled) {
          return;
        }
        settled = true;
        reject(new Error('The game server did not confirm the action in time.'));
      }, timeoutMs);

      socketRef.current.emit(event, payload, (response) => {
        if (settled) {
          return;
        }

        settled = true;
        window.clearTimeout(timerId);

        if (response?.ok === false) {
          reject(new Error(response.error || 'The server rejected the action.'));
          return;
        }

        resolve(response || { ok: true });
      });
    });
  }, [matchId]);

  const buildPropertyPayload = useCallback((propertyRef, extra = {}) => {
    const properties = useGameStore.getState().properties || {};
    const propertyByPosition = properties[propertyRef];
    if (propertyByPosition?.id != null) {
      return { property_id: propertyByPosition.id, ...extra };
    }

    const propertyById = Object.values(properties).find((property) => property.id === propertyRef);
    if (propertyById?.id != null) {
      return { property_id: propertyById.id, ...extra };
    }

    return { property_id: propertyRef, ...extra };
  }, []);

  const rollDice = useCallback(() => emit('roll_dice', {}), [emit]);
  const endTurn = useCallback(() => emit('end_turn', {}), [emit]);
  const buyProperty = useCallback(() => emit('buy_property', {}), [emit]);
  const declineProperty = useCallback(() => emit('decline_property', {}), [emit]);
  const placeBid = useCallback((amount) => emit('auction_bid', { amount }), [emit]);
  const submitTrade = useCallback((data) => emit('submit_trade', data), [emit]);
  const respondTrade = useCallback((tradeId, accept) => emit('respond_trade', { trade_id: tradeId, accept }), [emit]);
  const submitDeal = useCallback((data) => emitWithAck('submit_deal', data), [emitWithAck]);
  const respondDeal = useCallback((dealId, action) => emit('respond_deal', { deal_id: dealId, action }), [emit]);
  const counterDeal = useCallback((dealId, data) => emitWithAck('counter_deal', { deal_id: dealId, ...data }), [emitWithAck]);
  const cancelDeal = useCallback((dealId) => {
    clearActiveDeal();
    emit('cancel_deal', { deal_id: dealId });
  }, [clearActiveDeal, emit]);
  const submitLobby = useCallback((data) => emit('submit_lobby', data), [emit]);
  const submitNegotiation = useCallback((data) => emit('submit_negotiation', data), [emit]);
  const applyEmergencyReform = useCallback((data) => emit('apply_emergency_reform', data), [emit]);
  const developProperty = useCallback((propertyRef, options = {}) => emit('develop_property', buildPropertyPayload(propertyRef, options)), [emit, buildPropertyPayload]);
  const mortgageProperty = useCallback((propertyRef) => emit('mortgage_property', buildPropertyPayload(propertyRef)), [emit, buildPropertyPayload]);
  const sellHouse = useCallback((propertyRef) => emit('sell_house', buildPropertyPayload(propertyRef)), [emit, buildPropertyPayload]);
  const unmortgageProperty = useCallback((propertyRef) => emit('unmortgage_property', buildPropertyPayload(propertyRef)), [emit, buildPropertyPayload]);
  const declareBankruptcy = useCallback(() => emit('declare_bankruptcy', {}), [emit]);
  const payJailBail = useCallback(() => emit('pay_jail_bail', {}), [emit]);
  const useJailCard = useCallback(() => emit('use_jail_card', {}), [emit]);
  const selectColor = useCallback((color) => emit('select_color', { color }), [emit]);
  const setPlayerReady = useCallback((ready) => emit('player_ready', { ready }), [emit]);
  const updateSettings = useCallback((settings) => emit('update_settings', settings), [emit]);
  const startGame = useCallback(() => emit('start_game', {}), [emit]);

  return {
    socket: socketRef.current,
    emit,
    rollDice,
    endTurn,
    buyProperty,
    declineProperty,
    placeBid,
    submitTrade,
    respondTrade,
    submitDeal,
    respondDeal,
    counterDeal,
    cancelDeal,
    submitLobby,
    submitNegotiation,
    applyEmergencyReform,
    developProperty,
    mortgageProperty,
    sellHouse,
    unmortgageProperty,
    declareBankruptcy,
    payJailBail,
    useJailCard,
    selectColor,
    setPlayerReady,
    updateSettings,
    startGame,
  };
}
