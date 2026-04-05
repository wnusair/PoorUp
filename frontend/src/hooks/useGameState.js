import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';

function sortDeals(deals = []) {
  return [...(deals || [])].sort((left, right) => {
    const leftStamp = left.last_updated_at || left.accepted_at || left.responded_at || left.created_at || '';
    const rightStamp = right.last_updated_at || right.accepted_at || right.responded_at || right.created_at || '';
    return String(rightStamp).localeCompare(String(leftStamp));
  });
}

export const useGameStore = create(
  subscribeWithSelector((set, get) => ({
  // Game meta
  matchId: null,
  roomCode: null,
  gamePhase: 'lobby', // 'lobby' | 'playing' | 'ended'

  // Players
  players: [],
  currentPlayerId: null,
  myPlayerId: null,
  pendingDebts: [],

  // Board
  properties: {}, // { position: { owner_id, development_level, is_mortgaged, price, ... } }

  // Economy
  economy: {
    inflation_rate: 0,
    stability: 0.7,
    rage: 0,
    welfare_payout: 0,
    treasury_balance: 0,
    free_parking_pot: 0,
    bailout_enabled: false,
    gov_type: 'liberal_democracy',
    government_type: 'liberal_democracy',
    round_number: 1,
  },
  taxStats: {
    player_totals: {},
    totals: {},
    last_welfare_distribution: null,
    budget_history: [],
  },
  lobbyingStats: {
    player_totals: {},
    policy_pools: {},
    resolved_history: [],
  },
  playerFinanceHistory: {
    players: {},
    last_fingerprint: null,
  },
  social: {
    overall_rage: 0,
    stability_percent: 70,
    grievance_mix: {},
    territories: [],
    properties: {},
    active_incidents: [],
    unionized_property_count: 0,
    national_flashpoint: {},
  },

  // Game log
  logEntries: [],

  // UI state
  pendingAction: null, // { type: 'buy_property' | 'card_drawn' | 'auction' | ... , data: {} }
  activeModal: null,   // which modal is open
  diceResult: null,    // { die1, die2, total }
  diceRolledThisTurn: false,
  isRolling: false,
  diceRollTime: null,  // timestamp when dice_rolled event was received
  uprisingEvent: null,
  hyperInflation: null,
  auctionState: null,
  activeTrade: null,
  deals: [],
  activeDeal: null,
  awaitingEndTurnPlayerId: null,

  // Movement animation
  playerAnimPositions: {}, // playerId → current animated board position
  movingPlayerId: null,    // which player is currently animating
  pendingEventFns: [],     // functions queued while movement animation plays

  // Lobby
  lobbyData: null,
  settings: {},
  takenColors: [],

  // Actions
  setMatchId: (id) => set({ matchId: id }),
  setRoomCode: (code) => set({ roomCode: code }),
  setMyPlayerId: (id) => set({ myPlayerId: id }),
  setGamePhase: (phase) => set({ gamePhase: phase }),

  setPlayers: (players) => set({ players }),
  setPendingDebts: (pendingDebts) => set({ pendingDebts }),
  updatePlayer: (playerId, updates) =>
    set((state) => ({
      players: state.players.map((p) =>
        p.id === playerId ? { ...p, ...updates } : p
      ),
    })),

  setCurrentPlayerId: (id) => set({ currentPlayerId: id }),

  setProperties: (properties) => set({ properties }),
  updateProperty: (position, updates) =>
    set((state) => ({
      properties: {
        ...state.properties,
        [position]: { ...state.properties[position], ...updates },
      },
    })),

  setEconomy: (economy) => set({ economy }),
  updateEconomy: (updates) =>
    set((state) => ({ economy: { ...state.economy, ...updates } })),
  setTaxStats: (taxStats) => set({ taxStats }),
  setLobbyingStats: (lobbyingStats) => set({ lobbyingStats }),
  setPlayerFinanceHistory: (playerFinanceHistory) => set({ playerFinanceHistory }),
  setSocial: (social) => set({ social }),
  updateSocial: (updates) =>
    set((state) => ({ social: { ...state.social, ...updates } })),

  addLogEntry: (entry) =>
    set((state) => ({
      logEntries: [...state.logEntries, { ...entry, id: Date.now() + Math.random() }],
    })),
  setLogEntries: (entries) => set({ logEntries: entries }),

  setPendingAction: (action) => set({ pendingAction: action }),
  clearPendingAction: () => set({ pendingAction: null }),

  setActiveModal: (modal) => set({ activeModal: modal }),
  closeModal: () => {
    const state = get();
    const shouldResumeTrade =
      state.activeModal === 'card'
      && state.activeTrade
      && state.activeTrade.receiver_id === state.myPlayerId
      && !(state.auctionState?.active);

    set({
      activeModal: shouldResumeTrade ? 'trade' : null,
      activeDeal: shouldResumeTrade ? state.activeDeal : null,
    });
  },

  setDiceResult: (result) => set({ diceResult: result }),
  setDiceRolledThisTurn: (rolled) => set({ diceRolledThisTurn: rolled }),
  setIsRolling: (rolling) => set({ isRolling: rolling }),
  setDiceRollTime: (t) => set({ diceRollTime: t }),

  setPlayerAnimPos: (playerId, position) =>
    set((state) => ({
      playerAnimPositions: { ...state.playerAnimPositions, [playerId]: position },
    })),
  clearPlayerAnimPos: (playerId) =>
    set((state) => {
      const next = { ...state.playerAnimPositions };
      delete next[playerId];
      return { playerAnimPositions: next };
    }),
  setMovingPlayerId: (id) => set({ movingPlayerId: id }),
  queuePendingEvent: (fn) =>
    set((state) => ({ pendingEventFns: [...state.pendingEventFns, fn] })),
  flushPendingEvents: () => {
    const fns = get().pendingEventFns;
    set({ pendingEventFns: [] });
    fns.forEach((fn) => fn());
  },

  setUprisingEvent: (event) => set({ uprisingEvent: event }),
  clearUprising: () => set({ uprisingEvent: null }),

  setHyperInflation: (data) => set({ hyperInflation: data }),
  clearHyperInflation: () => set({ hyperInflation: null }),

  setAuctionState: (auction) => set({ auctionState: auction }),
  updateAuction: (updates) =>
    set((state) => ({
      auctionState: state.auctionState ? { ...state.auctionState, ...updates } : null,
    })),
  clearAuction: () => set({ auctionState: null }),

  setActiveTrade: (trade) => set({ activeTrade: trade }),
  clearTrade: () => set({ activeTrade: null }),

  setDeals: (deals) => set((state) => {
    const nextDeals = sortDeals(deals);
    const nextActiveDeal = state.activeDeal?.id != null
      ? nextDeals.find((deal) => deal.id === state.activeDeal.id) || state.activeDeal
      : state.activeDeal;

    return {
      deals: nextDeals,
      activeDeal: nextActiveDeal,
    };
  }),
  upsertDeal: (deal) => set((state) => {
    const nextDeals = state.deals.some((entry) => entry.id === deal.id)
      ? state.deals.map((entry) => (entry.id === deal.id ? { ...entry, ...deal } : entry))
      : [deal, ...state.deals];
    const sortedDeals = sortDeals(nextDeals);
    return {
      deals: sortedDeals,
      activeDeal: state.activeDeal?.id === deal.id ? { ...(state.activeDeal || {}), ...deal } : state.activeDeal,
    };
  }),
  setActiveDeal: (deal) => set({ activeDeal: deal }),
  clearActiveDeal: () => set({ activeDeal: null }),
  setAwaitingEndTurnPlayerId: (playerId) => set({ awaitingEndTurnPlayerId: playerId }),

  setLobbyData: (data) => set({ lobbyData: data }),
  setSettings: (settings) => set({ settings }),
  updateSettings: (updates) =>
    set((state) => ({ settings: { ...state.settings, ...updates } })),
  setTakenColors: (colors) => set({ takenColors: colors }),
  addTakenColor: (color) =>
    set((state) => ({ takenColors: [...new Set([...state.takenColors, color])] })),

  // Selectors
  getMe: () => {
    const { players, myPlayerId } = get();
    return players.find((p) => p.id === myPlayerId) || null;
  },
  getCurrentPlayer: () => {
    const { players, currentPlayerId } = get();
    return players.find((p) => p.id === currentPlayerId) || null;
  },
  isMyTurn: () => {
    const { myPlayerId, currentPlayerId } = get();
    return myPlayerId === currentPlayerId;
  },
  getPlayerById: (id) => {
    return get().players.find((p) => p.id === id) || null;
  },
}))
);

// Convenience hook
export function useGameState() {
  return useGameStore();
}
