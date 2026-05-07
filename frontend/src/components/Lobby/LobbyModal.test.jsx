import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useGameStore } from '../../hooks/useGameState';
import LobbyModal from './LobbyModal';

const mockedGameLobby = vi.fn();

vi.mock('../../utils/api', () => ({
  gameLobby: (...args) => mockedGameLobby(...args),
}));

function flushPromises() {
  return new Promise((resolve) => {
    setTimeout(resolve, 0);
  });
}

describe('LobbyModal', () => {
  beforeEach(() => {
    mockedGameLobby.mockReset();
    mockedGameLobby.mockResolvedValue({
      data: {
        message: 'Lobbying contribution submitted.',
        contributions: [
          {
            axis: 'tax_brackets',
            direction: 'rates_up',
            contribution: 120,
            policy: {
              axis_label: 'Tax Brackets',
              direction_label: 'Raise Rate',
            },
          },
        ],
        total_contribution: 120,
      },
    });

    act(() => {
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
  });

  afterEach(() => {
    act(() => {
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
  });

  it('shows plain-language liberal-democracy guidance and submits an explicit tax-bracket target', async () => {
    render(<LobbyModal matchId={12} onClose={() => {}} />);

    expect(screen.getByText('Tax Pyramid')).toBeInTheDocument();
    expect(screen.getByText(/tax brackets, treasury transfers, and money supply/i)).toBeInTheDocument();

    const taxBracketCard = screen.getByRole('heading', { name: /Tax Brackets/ }).closest('.rounded-3xl');
    expect(taxBracketCard).not.toBeNull();

    const raiseRateButton = within(taxBracketCard).getByText('Raise A Tax Bracket Rate').closest('[role="button"]');
    expect(raiseRateButton).not.toBeNull();
    await act(async () => {
      fireEvent.click(raiseRateButton);
      await flushPromises();
    });

    const amountInput = within(taxBracketCard).getByLabelText(/Contribution Amount/i);
    await act(async () => {
      fireEvent.change(amountInput, { target: { value: '120' } });
      await flushPromises();
    });

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Submit Contributions' }));
      await mockedGameLobby.mock.results[0]?.value;
      await flushPromises();
    });

    await waitFor(() => {
        expect(mockedGameLobby).toHaveBeenCalledWith(
          12,
          expect.objectContaining({
            contributions: [
              expect.objectContaining({
                axis: 'tax_brackets',
                direction: 'rates_up',
                target_stat: 'tax_bracket_rate_up',
                target: 'tax_bracket_rate_up',
                policy_name: 'Raise A Tax Bracket Rate',
                amount: 120,
              }),
            ],
        }),
      );
    });
  });
});
