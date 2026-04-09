import { describe, expect, it } from 'vitest';
import { normalizeSocial } from './gameState';


describe('normalizeSocial plot payloads', () => {
  it('normalizes plot state into predictable frontend shapes', () => {
    const social = normalizeSocial({
      plot: {
        exists: 1,
        founder_id: '2',
        stage: '3',
        support: '5.5',
        supply: '4',
        heat: '17',
        member_ids: ['2', '3'],
        committed_member_ids: ['2'],
        coalition_member_ids: ['4'],
        seized_property_ids: ['11'],
        regions: {
          Africa: {
            seeded_cells: '2',
            hardship_pressure: '3',
            defense_reserve: '1.5',
            safehouse_active: 1,
          },
        },
        seized_properties: [
          {
            property_id: '11',
            board_position: '4',
            current_value: '220',
            entrenchment: '2',
            supply_yield: '3',
            reintegration_progress: '50',
          },
        ],
        legal_targets: [
          {
            property_id: '12',
            owner_id: '4',
            board_position: '9',
            agitation: '2',
            preview_score: '14',
          },
        ],
        clusters: [
          {
            cluster_id: 'cluster_1',
            property_ids: ['11', '12'],
            size: '2',
            avg_entrenchment: '1.5',
            reintegration_pressure: '50',
            entrenched: 1,
            blockaded: 0,
            region_names: ['Africa'],
          },
        ],
        action_catalog: [
          {
            action_type: 'attempt_seizure',
            stage: '3',
            cooldown_rounds: '1',
            cost: { support: '6', supply: '4' },
          },
        ],
        counter_action_catalog: [
          {
            action_type: 'reintegration_campaign',
            cash_cost: '220',
            supporters_required: '1',
          },
        ],
        victory_countdown: {
          active: 1,
          rounds_held: '1',
          required_rounds: '2',
          completed: 0,
          countdown_eligible: 1,
        },
      },
    });

    expect(social.plot.exists).toBe(true);
    expect(social.plot.founder_id).toBe(2);
    expect(social.plot.member_ids).toEqual([2, 3]);
    expect(social.plot.committed_member_ids).toEqual([2]);
    expect(social.plot.coalition_member_ids).toEqual([4]);
    expect(social.plot.seized_properties[0].property_id).toBe(11);
    expect(social.plot.legal_targets[0].preview_score).toBe(14);
    expect(social.plot.clusters[0].property_ids).toEqual([11, 12]);
    expect(social.plot.regions.Africa.seeded_cells).toBe(2);
    expect(social.plot.action_catalog[0].cost.support).toBe(6);
    expect(social.plot.counter_action_catalog[0].cash_cost).toBe(220);
    expect(social.plot.victory_countdown.active).toBe(true);
    expect(social.plot.victory_countdown.rounds_held).toBe(1);
  });
});