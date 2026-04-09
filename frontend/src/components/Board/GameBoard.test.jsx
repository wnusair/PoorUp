import { render, screen } from '@testing-library/react';
import { beforeAll, describe, expect, it, vi } from 'vitest';

import { useGameStore } from '../../hooks/useGameState';
import GameBoard from './GameBoard';

beforeAll(() => {
  class ResizeObserverMock {
    observe() {}
    unobserve() {}
    disconnect() {}
  }

  vi.stubGlobal('ResizeObserver', ResizeObserverMock);
});

describe('GameBoard seized property rendering', () => {
  it('renders a single seized property tile without the cluster banner text', () => {
    useGameStore.setState({
      playerAnimPositions: {},
      movingPlayerId: null,
      economy: {},
    });

    const { container } = render(
      <GameBoard
        players={[]}
        properties={{
          12: {
            id: 12,
            board_position: 12,
            name: 'Istanbul',
            property_type: 'property',
            base_price: 140,
            group_color: '#8b5cf6',
            social_plot_seized: true,
            social_plot_cluster_id: 'solo-1',
          },
        }}
      />,
    );

    expect(screen.queryByText(/Property Of The People/i)).not.toBeInTheDocument();
    expect(container.querySelectorAll('img').length).toBeGreaterThan(0);
  });

  it('renders one shared banner across a seized cluster', () => {
    useGameStore.setState({
      playerAnimPositions: {},
      movingPlayerId: null,
      economy: {},
    });

    render(
      <GameBoard
        players={[]}
        properties={{
          36: {
            id: 36,
            board_position: 36,
            name: 'Buenos Aires',
            property_type: 'property',
            base_price: 270,
            group_color: '#22c55e',
            social_plot_seized: true,
            social_plot_cluster_id: 'cluster-a',
          },
          37: {
            id: 37,
            board_position: 37,
            name: 'Sao Paulo',
            property_type: 'property',
            base_price: 280,
            group_color: '#22c55e',
            social_plot_seized: true,
            social_plot_cluster_id: 'cluster-a',
          },
        }}
      />,
    );

    expect(screen.getAllByText(/Property Of The People/i)).toHaveLength(1);
  });
});