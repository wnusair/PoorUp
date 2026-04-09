import { describe, expect, it, vi } from 'vitest';
import { useGameStore } from '../hooks/useGameState';
import { applyLobbySnapshot, resolveLobbyPlayerId } from './lobbyState';


describe('lobby snapshot helpers', () => {
  it('resolves the current player from stored user identity', () => {
    const storage = {
      getItem: vi.fn((key) => (key === 'poorup_user' ? JSON.stringify({ id: 8 }) : null)),
    };
    Object.defineProperty(globalThis, 'localStorage', { value: storage, configurable: true });

    const playerId = resolveLobbyPlayerId([
      { id: 41, user_id: 8 },
      { id: 55, user_id: 9 },
    ]);

    expect(playerId).toBe(41);
  });

  it('applies lobby snapshots consistently across fetch and socket updates', () => {
    const storage = {
      getItem: vi.fn((key) => (key === 'poorup_user' ? JSON.stringify({ id: 3 }) : null)),
    };
    Object.defineProperty(globalThis, 'localStorage', { value: storage, configurable: true });

    useGameStore.setState({
      lobbyData: null,
      players: [],
      settings: {},
      takenColors: [],
      roomCode: null,
      matchId: null,
      myPlayerId: null,
    });

    applyLobbySnapshot({
      match: { id: 77, room_code: 'abcd' },
      players: [
        { id: 11, user_id: 3, username: 'Atlas', color_hex: '#3B82F6', is_ready: false },
        { id: 12, user_id: 4, username: 'Bot Prime', color_hex: '#EF4444', is_ready: true },
      ],
      settings: { government_type: 'Liberal Democracy' },
    }, { roomCode: 'ABCD' });

    const state = useGameStore.getState();
    expect(state.roomCode).toBe('ABCD');
    expect(state.matchId).toBe(77);
    expect(state.myPlayerId).toBe(11);
    expect(state.players).toHaveLength(2);
    expect(state.takenColors).toEqual(['#3B82F6', '#EF4444']);
    expect(state.settings.government_type).toBe('liberal_democracy');
  });
});