import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useGameStore } from '../../hooks/useGameState';
import LobbyRoom from './LobbyRoom';


const mockedNavigate = vi.fn();
const mockedLobbyAddBot = vi.fn();
const mockedLobbyGet = vi.fn();
const mockedLobbyRemoveBot = vi.fn();
const mockedLobbySetReady = vi.fn();
const mockedLobbyStart = vi.fn();
const mockedLobbyUpdateBot = vi.fn();
const mockedLobbyUpdateColor = vi.fn();
const mockedLobbyUpdateSettings = vi.fn();


vi.mock('react-router-dom', () => ({
  useNavigate: () => mockedNavigate,
}));


vi.mock('../../utils/api', () => ({
  lobbyAddBot: (...args) => mockedLobbyAddBot(...args),
  lobbyGet: (...args) => mockedLobbyGet(...args),
  lobbyRemoveBot: (...args) => mockedLobbyRemoveBot(...args),
  lobbySetReady: (...args) => mockedLobbySetReady(...args),
  lobbyStart: (...args) => mockedLobbyStart(...args),
  lobbyUpdateBot: (...args) => mockedLobbyUpdateBot(...args),
  lobbyUpdateColor: (...args) => mockedLobbyUpdateColor(...args),
  lobbyUpdateSettings: (...args) => mockedLobbyUpdateSettings(...args),
}));


function setLobbyStore(partial = {}) {
  useGameStore.setState({
    lobbyData: {
      match: {
        id: 91,
        room_code: 'ABCD',
        host_user_id: 7,
      },
      bot_setup: {
        defaults: {
          difficulty: 'normal',
          archetype_by_difficulty: { normal: 'liberal_democrat' },
        },
        difficulties: [
          { key: 'easy', label: 'Easy', summary: 'Low pressure.' },
          { key: 'normal', label: 'Normal', summary: 'Balanced.' },
        ],
        archetypes: [
          {
            key: 'liberal_democrat',
            label: 'Liberal Democrat',
            short_description: 'Balanced market-first play.',
            example_behaviors: ['Builds steadily.'],
            preferred_doctrines: ['capital_markets_arbitrage'],
            default_personality_by_difficulty: {
              easy: 'steady_collector',
              normal: 'balanced',
            },
          },
        ],
      },
    },
    players: [
      {
        id: 1,
        user_id: 7,
        username: 'Atlas',
        color_hex: '#3B82F6',
        is_ready: false,
        is_bot: false,
      },
    ],
    settings: {
      max_players: 6,
      government_type: 'liberal_democracy',
    },
    takenColors: ['#3B82F6'],
    myPlayerId: 1,
    gamePhase: 'lobby',
    roomCode: 'ABCD',
    matchId: 91,
    ...partial,
  });
}

function flushPromises() {
  return new Promise((resolve) => {
    setTimeout(resolve, 0);
  });
}


describe('LobbyRoom', () => {
  beforeEach(() => {
    mockedNavigate.mockReset();
    mockedLobbyAddBot.mockReset();
    mockedLobbyGet.mockReset();
    mockedLobbyRemoveBot.mockReset();
    mockedLobbySetReady.mockReset();
    mockedLobbyStart.mockReset();
    mockedLobbyUpdateBot.mockReset();
    mockedLobbyUpdateColor.mockReset();
    mockedLobbyUpdateSettings.mockReset();

    const storage = {
      getItem: vi.fn((key) => (key === 'poorup_user' ? JSON.stringify({ id: 7 }) : null)),
    };
    Object.defineProperty(globalThis, 'localStorage', {
      value: storage,
      configurable: true,
    });

    act(() => {
      setLobbyStore();
    });
  });

  afterEach(() => {
    act(() => {
      useGameStore.setState({
        lobbyData: null,
        players: [],
        settings: {},
        takenColors: [],
        myPlayerId: null,
        gamePhase: 'lobby',
        roomCode: null,
        matchId: null,
      });
    });
  });

  it('applies the returned lobby snapshot after adding a bot', async () => {
    mockedLobbyAddBot.mockResolvedValue({
      data: {
        lobby: {
          match: {
            id: 91,
            room_code: 'ABCD',
            host_user_id: 7,
          },
          players: [
            { id: 1, user_id: 7, username: 'Atlas', color_hex: '#3B82F6', is_ready: false, is_bot: false },
            { id: 2, user_id: null, username: 'Bot Prime', color_hex: '#EF4444', is_ready: false, is_bot: true },
          ],
          settings: {
            max_players: 6,
            government_type: 'liberal_democracy',
          },
          taken_colors: ['#3B82F6', '#EF4444'],
          bot_setup: useGameStore.getState().lobbyData.bot_setup,
        },
      },
    });

    render(<LobbyRoom roomCode="ABCD" />);

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Bot Setup' }));
      await flushPromises();
    });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Add Bots' }));
      await mockedLobbyAddBot.mock.results[0]?.value;
      await flushPromises();
    });

    await waitFor(() => {
      expect(mockedLobbyAddBot).toHaveBeenCalledWith(
        'ABCD',
        expect.objectContaining({ count: 1, difficulty: 'normal', archetype: 'liberal_democrat' }),
      );
    });

    await waitFor(() => {
      expect(useGameStore.getState().players.some((player) => player.username === 'Bot Prime')).toBe(true);
    });
    expect(useGameStore.getState().players).toHaveLength(2);
    expect(useGameStore.getState().takenColors).toEqual(['#3B82F6', '#EF4444']);
  });

  it('applies the returned lobby snapshot after changing color', async () => {
    mockedLobbyUpdateColor.mockResolvedValue({
      data: {
        lobby: {
          match: {
            id: 91,
            room_code: 'ABCD',
            host_user_id: 7,
          },
          players: [
            { id: 1, user_id: 7, username: 'Atlas', color_hex: '#4CAF50', is_ready: false, is_bot: false },
          ],
          settings: {
            max_players: 6,
            government_type: 'liberal_democracy',
          },
          taken_colors: ['#4CAF50'],
          bot_setup: useGameStore.getState().lobbyData.bot_setup,
        },
      },
    });

    render(<LobbyRoom roomCode="ABCD" />);

    await act(async () => {
      fireEvent.click(screen.getByTitle('#4CAF50'));
      await mockedLobbyUpdateColor.mock.results[0]?.value;
      await flushPromises();
    });

    expect(mockedLobbyUpdateColor).toHaveBeenCalledWith('ABCD', '#4CAF50');
    await waitFor(() => {
      expect(useGameStore.getState().players[0].color_hex).toBe('#4CAF50');
    });
    expect(useGameStore.getState().takenColors).toEqual(['#4CAF50']);
  });

  it('applies the returned lobby snapshot after toggling ready', async () => {
    mockedLobbySetReady.mockResolvedValue({
      data: {
        lobby: {
          match: {
            id: 91,
            room_code: 'ABCD',
            host_user_id: 7,
          },
          players: [
            { id: 1, user_id: 7, username: 'Atlas', color_hex: '#3B82F6', is_ready: true, is_bot: false },
          ],
          settings: {
            max_players: 6,
            government_type: 'liberal_democracy',
          },
          taken_colors: ['#3B82F6'],
          bot_setup: useGameStore.getState().lobbyData.bot_setup,
        },
      },
    });

    render(<LobbyRoom roomCode="ABCD" />);

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Mark Ready' }));
      await mockedLobbySetReady.mock.results[0]?.value;
      await flushPromises();
    });

    expect(mockedLobbySetReady).toHaveBeenCalledWith('ABCD', true);
    await waitFor(() => {
      expect(useGameStore.getState().players[0].is_ready).toBe(true);
    });
  });
});
