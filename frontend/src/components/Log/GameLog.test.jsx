import { act, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { useGameStore } from '../../hooks/useGameState';
import GameLog from './GameLog';

describe('GameLog auto-scroll', () => {
  beforeEach(() => {
    act(() => {
      useGameStore.setState({
        players: [
          {
            id: 1,
            username: 'Atlas',
            color_hex: '#ff6600',
          },
        ],
        logEntries: [],
      });
    });
  });

  afterEach(() => {
    act(() => {
      useGameStore.setState({
        players: [],
        logEntries: [],
      });
    });
  });

  it('scrolls to the bottom when a new log entry is appended', async () => {
    render(<GameLog />);

    const container = screen.getByLabelText('Game log entries');
    let currentScrollTop = 0;

    Object.defineProperty(container, 'scrollHeight', {
      configurable: true,
      get: () => 180,
    });

    Object.defineProperty(container, 'scrollTop', {
      configurable: true,
      get: () => currentScrollTop,
      set: (value) => {
        currentScrollTop = value;
      },
    });

    act(() => {
      useGameStore.setState({
        logEntries: [
          {
            id: 'entry-1',
            type: 'move',
            message: 'Atlas rolled a 7',
            timestamp: '2026-04-17T10:00:00Z',
            player_id: 1,
          },
        ],
      });
    });

    await waitFor(() => {
      expect(currentScrollTop).toBe(180);
    });

    Object.defineProperty(container, 'scrollHeight', {
      configurable: true,
      get: () => 360,
    });

    act(() => {
      useGameStore.setState({
        logEntries: [
          {
            id: 'entry-1',
            type: 'move',
            message: 'Atlas rolled a 7',
            timestamp: '2026-04-17T10:00:00Z',
            player_id: 1,
          },
          {
            id: 'entry-2',
            type: 'rent_collected',
            message: 'Atlas collected rent',
            timestamp: '2026-04-17T10:00:05Z',
            player_id: 1,
          },
        ],
      });
    });

    await waitFor(() => {
      expect(currentScrollTop).toBe(360);
    });
  });
});