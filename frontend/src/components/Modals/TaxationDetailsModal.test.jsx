import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import TaxationDetailsModal from './TaxationDetailsModal';
import { useGameStore } from '../../hooks/useGameState';


function seedStore() {
  useGameStore.setState({
    myPlayerId: 1,
    players: [
      { id: 1, username: 'Atlas', balance: 1200, bankrupt: false },
      { id: 2, username: 'Rival', balance: 850, bankrupt: false },
    ],
    properties: {
      4: {
        id: 11,
        board_position: 4,
        owner_id: 1,
        current_value: 180,
        is_mortgaged: false,
        property_type: 'property',
      },
    },
    economy: {
      tax_multiplier: 0.25,
      gov_type: 'liberal_democracy',
      government_type: 'liberal_democracy',
      round_number: 4,
      inflation_rate: 0.03,
      treasury_balance: 1400,
      welfare_payout: 18,
      free_parking_pot: 90,
      bailout_enabled: true,
    },
    settings: {
      income_tax_on_pass_go: true,
      property_tax_every_n_rounds: 1,
      tax_every_turn: true,
      government_type: 'liberal_democracy',
    },
    taxStats: {
      player_totals: {
        '1': {
          income_tax: 120,
          property_tax: 10,
          turn_tax: 12,
          luxury_tax: 0,
          super_tax: 0,
          total_tax_paid: 142,
          welfare_contributed: 0,
          welfare_received: 0,
        },
      },
      totals: {
        income_tax: 120,
        property_tax: 10,
        turn_tax: 12,
        luxury_tax: 0,
        super_tax: 0,
        total_tax_paid: 142,
      },
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
  });
}


describe('TaxationDetailsModal', () => {
  beforeEach(() => {
    seedStore();
  });

  it('shows the live round tax preview inside the taxation tab', () => {
    render(<TaxationDetailsModal onClose={() => {}} />);

    expect(screen.getByText('Round 4 Tax Preview')).toBeInTheDocument();
    expect(screen.getByText('Guaranteed Per Turn')).toBeInTheDocument();
    expect(screen.getByText('Guaranteed Per Rotation')).toBeInTheDocument();
    expect(screen.getByText('Tax Rules')).toBeInTheDocument();
    expect(screen.getByText('Per-Player Tax Totals')).toBeInTheDocument();
  });
});