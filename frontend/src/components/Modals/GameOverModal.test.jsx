import { act, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useGameStore } from '../../hooks/useGameState';
import GameOverModal from './GameOverModal';


vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
}));


describe('GameOverModal faction winners', () => {
  afterEach(() => {
    act(() => {
      useGameStore.setState({
        pendingAction: null,
        players: [],
        properties: {},
      });
    });
  });

  it('renders communist faction winners and committed members', () => {
    act(() => {
      useGameStore.setState({
        pendingAction: {
          data: {
            winner: {
              type: 'faction',
              label: "People's Victory",
              committed_members: [
                { id: 1, username: 'Atlas' },
                { id: 2, username: 'Mila' },
              ],
              control_percent: 31.4,
              victory_round: 12,
            },
            round: 12,
          },
        },
        players: [
          { id: 1, username: 'Atlas', color_hex: '#ef4444', is_bankrupt: false, balance: 1200 },
          { id: 2, username: 'Mila', color_hex: '#f59e0b', is_bankrupt: false, balance: 900 },
        ],
        properties: {},
      });
    });

    render(<GameOverModal />);

    expect(screen.getByText('Faction Victory')).toBeInTheDocument();
    expect(screen.getByText("People's Victory")).toBeInTheDocument();
    expect(screen.getByText('Atlas • Mila')).toBeInTheDocument();
    expect(screen.getByText('Control held: 31.4% • Round 12')).toBeInTheDocument();
  });
});