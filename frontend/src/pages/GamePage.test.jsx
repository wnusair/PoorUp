import { render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useGameStore } from '../hooks/useGameState';
import GamePage from './GamePage';


const mockedNavigate = vi.fn();
const mockedSocketEmit = vi.fn();
const mockedUseSocket = vi.fn(() => ({}));
const mockedApiGet = vi.fn();


vi.mock('react-router-dom', () => ({
  useParams: () => ({ matchId: '77' }),
  useNavigate: () => mockedNavigate,
}));


vi.mock('../hooks/useSocket', () => ({
  getSocket: () => ({ emit: mockedSocketEmit }),
  useSocket: (args) => mockedUseSocket(args),
}));


vi.mock('../components/Game/GameLayout', () => ({
  default: () => <div>Game Layout</div>,
}));


vi.mock('../utils/api', () => ({
  api: {
    get: (...args) => mockedApiGet(...args),
  },
}));


describe('GamePage socket handoff', () => {
  beforeEach(() => {
    mockedNavigate.mockReset();
    mockedSocketEmit.mockReset();
    mockedUseSocket.mockClear();
    mockedApiGet.mockReset();
    mockedApiGet.mockResolvedValue({
      data: {
        state: {
          players: [
            {
              id: 1,
              user_id: 7,
              username: 'Atlas',
              balance: 1500,
              current_position: 0,
              is_bankrupt: false,
            },
          ],
          properties: [],
          social: {},
          pending_debts: [],
          deals: [],
          econ: {},
          settings: {},
          current_player_id: 1,
          dice_rolled_this_turn: false,
        },
      },
    });

    const storage = {
      getItem: vi.fn((key) => (key === 'poorup_user' ? JSON.stringify({ id: '7' }) : null)),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
    };
    Object.defineProperty(window, 'localStorage', {
      value: storage,
      configurable: true,
    });
    Object.defineProperty(globalThis, 'localStorage', {
      value: storage,
      configurable: true,
    });

    useGameStore.setState({
      myPlayerId: null,
      matchId: null,
      roomCode: 'ABCD',
      gamePhase: 'lobby',
      players: [],
      properties: {},
      economy: {},
      social: {},
      settings: {},
      deals: [],
      pendingDebts: [],
      pendingAction: null,
      activeModal: null,
      diceResult: null,
      diceRolledThisTurn: false,
      isRolling: false,
      awaitingEndTurnPlayerId: null,
      taxStats: null,
      lobbyingStats: null,
      playerFinanceHistory: null,
    });
  });

  afterEach(() => {
    useGameStore.setState({
      myPlayerId: null,
      matchId: null,
      roomCode: null,
      gamePhase: 'lobby',
      players: [],
      properties: {},
      economy: {},
      social: {},
      settings: {},
      deals: [],
      pendingDebts: [],
      pendingAction: null,
      activeModal: null,
      diceResult: null,
      diceRolledThisTurn: false,
      isRolling: false,
      awaitingEndTurnPlayerId: null,
      taxStats: null,
      lobbyingStats: null,
      playerFinanceHistory: null,
    });
  });

  it('connects the game socket immediately and rejoins the match room after state fetch', async () => {
    render(<GamePage />);

    expect(mockedUseSocket).toHaveBeenCalledWith(
      expect.objectContaining({
        matchId: 77,
        roomCode: 'ABCD',
        enabled: true,
      }),
    );

    await waitFor(() => {
      expect(useGameStore.getState().myPlayerId).toBe(1);
    });

    expect(mockedSocketEmit).toHaveBeenCalledWith('join_room', {
      room_code: 'ABCD',
      match_id: 77,
    });
  });
});