import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useGameStore } from '../../hooks/useGameState';
import LobbyModal from './LobbyModal';

const mockedGameLobby = vi.fn();

vi.mock('../../utils/api', () => ({
  gameLobby: (...args) => mockedGameLobby(...args),
}));

describe('LobbyModal', () => {
  beforeEach(() => {
    mockedGameLobby.mockReset();
    mockedGameLobby.mockResolvedValue({
      data: {
        message: 'Lobbying contribution submitted.',
        contributions: [
          {
            axis: 'cash_bonus',
            direction: 'increase',
            contribution: 120,
            policy: {
              axis_label: 'Cash Bonus',
              direction_label: 'Increase',
            },
          },
        ],
        total_contribution: 120,
      },
    });

    useGameStore.setState({
      players: [
        { id: 1, username: 'Atlas', balance: 900 },
        { id: 2, username: 'Rival', balance: 500 },
      ],
      myPlayerId: 1,
      economy: {
        gov_type: 'Liberal Democracy',
        government_type: 'Liberal Democracy',
        market_confidence: 78,
        capital_yield_rate: 0.024,
        capital_yield_reserve_floor: 200,
        stability: 0.63,
        bailout_enabled: false,
      },
      settings: {
        government_type: 'Liberal Democracy',
      },
      lobbyingStats: {
        player_totals: {},
        policy_pools: {},
        resolved_history: [],
      },
    });
  });

  afterEach(() => {
    useGameStore.setState({
      players: [],
      myPlayerId: null,
      settings: {},
      lobbyingStats: {
        player_totals: {},
        policy_pools: {},
        resolved_history: [],
      },
    });
  });

  it('shows plain-language liberal-democracy guidance and submits an explicit cash-bonus target', async () => {
    render(<LobbyModal matchId={12} onClose={() => {}} />);

    expect(screen.getByText('Direct payout button')).toBeInTheDocument();
    expect(screen.getByText(/Cash Bonus is the direct payout lever/i)).toBeInTheDocument();

    const cashBonusCard = screen.getByRole('heading', { name: /Cash Bonus/ }).closest('.rounded-3xl');
    expect(cashBonusCard).not.toBeNull();

    const increaseButton = within(cashBonusCard).getByText('Increase Cash Bonus').closest('button');
    expect(increaseButton).not.toBeNull();
    fireEvent.click(increaseButton);

    const amountInput = within(cashBonusCard).getByLabelText(/Contribution Amount/i);
    fireEvent.change(amountInput, { target: { value: '120' } });

    fireEvent.click(screen.getByRole('button', { name: 'Submit Contributions' }));

    await waitFor(() => {
      expect(mockedGameLobby).toHaveBeenCalledWith(
        12,
        expect.objectContaining({
          contributions: [
            expect.objectContaining({
              axis: 'cash_bonus',
              direction: 'increase',
              target_stat: 'cash_bonus_increase',
              target: 'cash_bonus_increase',
              policy_name: 'Increase Cash Bonus',
              amount: 120,
            }),
          ],
        }),
      );
    });
  });
});