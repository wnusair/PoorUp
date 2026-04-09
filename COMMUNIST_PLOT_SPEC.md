# Communist Plot Spec

## Goal

Add a new Plot panel and a full communist revolution path that acts as a real comeback system for players who were unlucky early, while remaining beatable through planning, coalition play, reform, and direct counter-pressure.

This path should feel like a player is no longer playing as a normal landlord and is instead organizing, radicalizing, seizing, and defending territory as a revolutionary movement. It must not be a hidden instant-win button, a stronger rent engine, or a one-turn board flip.

## Design Pillars

1. The Plot path is a comeback mechanic, not an opening strategy.
2. The Plot path advances through a visible multi-round arc with commitment, setbacks, and counterplay.
3. Seized land should generate most of its value through end-of-round extraction and revolutionary logistics, not through abusive landing fees.
4. Communist victory is shared by committed members when there are multiple, but joining requires real work and real sacrifice rather than being mandatory for the win.
5. Non-communist players must have equally strategic answers: relief, reform, defense, coalition funding, intelligence, and reintegration.
6. The board must make seized territory unmistakable at a glance through aggressive red takeover visuals and cluster-aware overlays.

## Player-Facing Fantasy

- A struggling player discovers an alternative path instead of waiting to be eliminated.
- They begin underground, organize cells, recruit support, survive discovery, and convert unrest into directed revolutionary power.
- Once land is seized, the faction stops acting like a normal property owner. It extracts Supply from controlled territory and spends that Supply to spread or defend the revolution.
- Other players can join through a real political process, not a single button press.
- Non-communists can respond together through planned countermeasures instead of hoping the system burns out by itself.
- The endgame is not one explosive moment. The revolutionary faction must survive as a rival power long enough to prove it can govern.

## Availability And Entry Rules

### Basic Availability

- The Plot panel exists for every player, every game, alongside Economy, Stability, Deals, and Lobbying.
- Before a plot exists, most players see a locked or informational version of the panel.
- The panel becomes actionable for players who meet hardship requirements.
- The panel remains useful for non-communists after the plot goes public because it becomes the main counter-revolution and intelligence view.

### Founding Eligibility

A player may found the communist plot only if all of the following are true:

1. The match is at or after round 4.
2. The player is not bankrupt.
3. The player is not currently the wealthiest active player.
4. The player meets at least 2 hardship triggers.

### Hardship Triggers

Use the following hardship triggers in v1:

1. Current balance is at or below 65% of the median active-player balance.
2. Net worth has been in the bottom half of active players for 2 consecutive rounds.
3. The player lost a property, failed a critical auction, or had a deal collapse in the last 2 rounds.
4. The player has pending debt, recently required a bailout, or is within one serious hit of bankruptcy.
5. The player owns no full monopoly and has 2 or fewer total properties after round 4.

### Minarchism Modifier

Under minarchism, concentrated overdevelopment should make ignition easier.

- If a dominant owner in the founding player's region has heavy development, add hidden hardship pressure.
- Recommended v1 rule: every 2 development levels across the dominant owner's local cluster adds +1 hardship pressure, up to +3.
- This does not remove counterplay. It only makes the local social powder keg easier to light.

### Founding Action

- Founding the plot consumes the player's once-per-turn political action.
- Founding does not require cash.
- Founding grants initial Support equal to 4 + hardship pressure, capped at 8.
- Founding sets the player to `founder` and `underground_member`.
- Only one communist plot exists at a time in a match.

## Revolution Arc

The Plot path uses a five-stage progression. A faction may advance by at most one stage per round. This alone prevents one-turn revolution wins.

| Stage | Name | Minimum Round | Requirements | Unlocks |
|---|---|---:|---|---|
| 0 | Eligible Hardship | 4 | Hardship triggers met | Found plot, view recruitment hooks |
| 1 | Underground Cell | 4 | Founder starts plot | Mutual aid, whisper campaigns, local cell seeding |
| 2 | Agitation Network | 5 | 12 total Support generated, 2 seeded cells, Heat below 60 | Recruitment, agitation actions, sabotage, district targeting |
| 3 | Open Seizure | 6 | 1 committed member, 6 Support, 4 Supply, one legal seizure target | Public faction, first property seizure, solidarity levies |
| 4 | Dual Power | 7 | 4 seized properties or 18% board value, 1 entrenched cluster, Support above 12 | Regional councils, supply scaling, victory countdown eligibility |
| 5 | People's Victory | 9 | 30% board value or 8 seized properties across 2 regions, 1 committed member, 2 full rounds held | Match ends in shared faction victory |

### Stage 1: Underground Cell

This is the quiet buildup phase.

- The plot is hidden from other players except for vague instability hints already surfaced by the social system.
- The founder can perform only soft-power actions.
- The goal is to generate Support, establish target regions, and survive without exposing the faction too early.

Available actions:

1. Mutual Aid
2. Whisper Campaign
3. Establish Safehouse
4. Seed Cell In Region

### Stage 2: Agitation Network

This is the organizing phase.

- The faction starts shaping specific territories.
- Agitation grows on targeted properties and regions rather than across the whole board.
- Joining becomes possible for other players, but not yet cheap or automatic.
- The faction can prepare a seizure without immediately executing it.

Available actions:

1. Recruit Sympathizer
2. Convert Sympathizer To Organizer
3. Agitate Property
4. Sabotage Development
5. Hide Assets
6. Stockpile Supply

### Stage 3: Open Seizure

This is the public break with the old order.

- The plot becomes visible to all players.
- The first successful seizure changes the board state visibly and unlocks anti-revolution coalition play.
- The faction begins generating Supply from seized land.
- Landing on seized land now uses a special solidarity levy rather than standard rent.

Available actions:

1. Attempt Seizure
2. Fortify Seized Property
3. Spread To Adjacent Territory
4. Recruit Publicly
5. Call Emergency Redistribution

### Stage 4: Dual Power

This is the sustained rival-government phase.

- The faction should now feel like it controls part of the map.
- It can no longer behave like a standard property-growth strategy.
- The faction is expected to spend Supply on maintaining and expanding control, not hoard cash.
- Non-communist players should now have clear, coordinated methods to push back.

Available actions:

1. Establish Regional Council
2. Increase Entrenchment
3. Redirect Supply Between Regions
4. Call Mass Action
5. Defend Against Reintegration

### Stage 5: People's Victory

Victory is shared by fully committed communist members if, and only if, the faction survives as a rival power.
A solo founder must be able to complete this countdown alone; extra committed members make the hold easier and share the win, but they are not a hard gate.

Recommended v1 victory rule:

1. At least 1 committed member must still be active.
2. The faction must control at least 30% of total active board value or 8 properties across at least 2 regions.
3. At least 2 seized clusters must be entrenched.
4. These conditions must hold at 2 consecutive round-end resolutions.
5. If any condition fails during the hold window, the countdown resets.

This turns victory into a defendable countdown rather than a jump-scare finish.

## Revolutionary Economy

The communist path should not primarily care about collecting giant rent off unlucky landings. It should care about extracting political and material capacity from controlled land.

Use 3 plot metrics in v1:

1. Support: political backing and movement momentum.
2. Supply: logistical output and usable revolutionary capacity.
3. Heat: exposure, repression pressure, and public vulnerability.

### Support

Support is generated by hardship, care work, class tension, and successful resistance.

Support sources:

1. Founding hardship bonus.
2. Mutual aid actions.
3. Successful recruitment.
4. Surviving crackdowns.
5. Defending seized territory.
6. Treasury distress, concentrated ownership, and visible landlord excess in affected regions.

Support sinks:

1. Recruitment.
2. Agitation.
3. Seizure attempts.
4. Public messaging.
5. Emergency defense against reintegration.

Support decay:

- If the faction controls seized territory but performs no mutual aid or recruitment for 2 rounds, Support decays by 2 per round.
- This prevents a pure land-hoarding, no-politics strategy.

### Supply

Supply is the communist faction's material economy.

- Supply is generated at round end from seized land.
- Supply is used for seizures, fortification, spread, entrenchment, and victory defense.
- Supply does not replace cash for ordinary player actions outside the plot path.
- Once a player becomes a committed member, they should be heavily discouraged from continuing normal capitalist expansion.

### Heat

Heat exists to stop runaway secrecy and to create windows for counterplay.

Heat rises from:

1. Public seizures.
2. Failed operations.
3. Fast back-to-back expansion.
4. Harsh solidarity levies.
5. Public recruitment.

Heat falls from:

1. Safehouse actions.
2. Successful mutual aid.
3. Skipping aggression for a round.
4. Holding without overextending.

Heat thresholds:

1. At 40 Heat, the faction becomes easier to detect and coalition scouting gets cheaper.
2. At 60 Heat, hidden-cell actions lose efficiency.
3. At 85 Heat, the faction may not start the victory countdown.

## Seized Land Output

Seized properties should generate variable output based on the land itself, not just on who lands there.

### Recommended Supply Yield Formula

At end of each round, every seized property generates:

`Supply Yield = Base Tier + Development Bonus + Contiguous Cluster Bonus + Volatility - Blockade Penalty - Exhaustion Penalty`

Recommended components:

1. Base Tier: `1 + floor(base_price / 180)`, capped at 4.
2. Development Bonus: `min(dev_level, 3)`.
3. Contiguous Cluster Bonus: `+1` for 2 connected seized properties, `+2` for 3 or more, capped at 2.
4. Volatility: `-1, 0, or +1` based on region instability, active crackdowns, and recent unrest resolution.
5. Blockade Penalty: `-2` while anti-revolution coalition blockade is active on the cluster.
6. Exhaustion Penalty: `-1` if the same property funded a levy and a spread action in the same round.

Clamp final yield between 0 and 8.

### Why This Is Balanced

- Rich property clusters matter.
- Development matters.
- Contiguous expansion matters.
- Overuse and blockades matter.
- The faction does not get infinite power from a single hot property.

### Minarchism Development Rule

Under minarchism, houses and hotels should make revolutionary ignition easier and first seizure more explosive.

Recommended v1 modifier:

1. Development Bonus counts as `min(dev_level, 4)` on first seizure in minarchism.
2. The same property adds +1 Heat for every 2 development levels.
3. Entrenched reintegration rewards are also stronger there, so coalition retakes are more lucrative.

This produces the intended flavor: overbuilt minarchist enclaves are the easiest places to ignite, but the hardest places to hold cleanly.

## Solidarity Levies

Landing on seized land should not simply become a stronger rent trap.

### Rule Direction

- Replace normal rent on seized property with a smaller, bounded solidarity levy.
- The levy is secondary income. The primary economy is the end-of-round Supply yield.

### Recommended Levy Rule

`Solidarity Levy = min(0.8 * normal_rent + entrenchment_bonus, levy_cap)`

Recommended tuning:

1. Entrenchment bonus: +10, +20, or +30 by entrenchment level.
2. Levy cap: `min(180, 0.15 * target_net_worth)`.
3. Communist members do not pay the levy.
4. Coalition members pay the levy unless they have a temporary passage effect.

This keeps seized land relevant on movement without turning it into an unstoppable rent engine.

## Plot Actions

Use explicit costs and cooldowns so the faction feels structured and beatable.

| Action | Stage | Cost | Cooldown | Outcome |
|---|---|---|---|---|
| Mutual Aid | 1 | 2 Support | 1 round per region | Gain Support, reduce Heat, improve recruitment odds |
| Whisper Campaign | 1 | 1 Support | None | Increase local agitation slightly |
| Seed Cell | 1 | 3 Support | 1 round per region | Creates hidden local foothold |
| Recruit Sympathizer | 2 | 4 Support | 1 round per target | Starts join process for another player |
| Convert To Organizer | 2 | 2 Support + 1 Supply | 1 round per target | Unlocks real contribution actions |
| Agitate Property | 2 | 2 Support | 1 round per property | Raises plot pressure on target property |
| Sabotage Development | 2 | 1 Supply + 1 Support | 2 rounds per property | Cuts owner efficiency, raises tension |
| Attempt Seizure | 3 | 6 Support + 4 Supply | 1 faction attempt per round | Seizes one qualifying property on success |
| Fortify Property | 3 | 2 Supply | 1 round per property | Raises entrenchment and supply defense |
| Spread To Adjacent Territory | 3 | 3 Support + 2 Supply | 1 round per cluster | Opens expansion target |
| Establish Regional Council | 4 | 5 Supply + 3 Support | 2 rounds per region | Unlocks victory progress in region |
| Defend Reintegration | 4 | 3 Supply | Reactive | Lowers reintegration progress |
| Call Mass Action | 4 | 5 Support | 2 rounds global | Burst Support, burst Heat |

### Anti-Abuse Rails

1. No more than one seizure attempt per faction per round before Dual Power.
2. The faction may not trigger the victory countdown in the same round as its first seizure.
3. A failed seizure locks the target property against another seizure for 2 rounds.
4. Supply above 25 decays by 20% each round to discourage pure hoarding.
5. Support above 40 while the plot is still underground bleeds 2 per round into Heat.

## Joining The Revolution

Other players must be able to join, but only by following a real process.
Joining should strengthen the faction and broaden shared victory, not act as a mandatory unlock for solo success.

### Membership States

1. Observer
2. Sympathizer
3. Organizer
4. Committed Member
5. Cadre

### Join Flow

1. A current member targets a player with a recruit action.
2. The target becomes a Sympathizer if they accept and either meet hardship or pay a higher political cost.
3. A Sympathizer must contribute across at least 2 separate rounds to become an Organizer.
4. An Organizer becomes a Committed Member only after participating in one successful movement action such as defense, agitation, or seizure support.
5. Only Committed Members share victory.

### Prosperous Joiners

Not every joiner should be poor.

- Players above median wealth may join after the plot goes public.
- They must pay double contribution requirements to become Committed Members.
- This allows ideological or opportunistic converts without making rich players the easiest founders.

### Leaving Or Defecting

- A Committed Member may leave only during their turn.
- Leaving costs half their lifetime Support contribution and triggers a 3-round re-entry cooldown.
- Public defection lowers faction Support but also lowers Heat.
- Defection during an active victory countdown lowers the countdown immediately by one step.

## Non-Communist Counterplay

The opposition must be able to win through planning, not just by hoping the faction runs out of steam.

### Anti-Revolution Coalition

The anti-revolution coalition becomes available after the first successful public seizure.

- Any non-communist player may join.
- Coalition membership does not share rent or normal victory.
- Coalition members may pool money and action points into counter-revolution operations.

### Coalition Actions

| Action | Cost | Outcome | Backfire Risk |
|---|---|---|---|
| Relief Package | Cash + treasury help | Lowers hardship and Support growth in one region | Low |
| Labor Settlement | Cash | Reduces agitation and negotiation pressure on one property | Low |
| Security Subsidy | Cash | Makes a property harder to seize for 2 rounds | Medium |
| Intelligence Sweep | Cash + action | Reveals hidden cells or regional plans | High if it fails |
| Blockade Cluster | Cash + coalition support | Reduces Supply yield on a seized cluster | Medium |
| Reintegration Campaign | Cash + sustained pressure | Reclaims a seized property after 2 successful pushes | High |
| Propaganda Counteroffensive | Cash or lobbying contribution | Slows recruitment globally for one round | Medium |

### Counterplay Principles

1. Relief and reform are cleaner and safer but slower.
2. Crackdowns are faster but create backlash if used against genuinely distressed populations.
3. Blockades and reintegration should require repeated commitment, not one-click reversals.
4. Non-communists should need coordination to defeat a mature revolution just as the faction needs coordination to win.

### Backlash Rule

Repression without relief should feed the revolution.

Recommended v1 rule:

- If an Intelligence Sweep, Security Subsidy, or Reintegration Campaign is used in a region whose hardship pressure is still high, grant the plot +1 to +3 Support based on distress level.

This keeps the answer from being "always click crackdown."

## Government-Specific Behavior

### Liberal Democracy

- Easier recruitment through inequality, extraction pressure, and confidence shocks.
- Better reform and lobbying counterplay than minarchism.
- Market-rich areas create strong Supply if seized.
- Confidence-stabilizing policies are a major anti-revolution tool.

### Social Democracy

- Welfare and relief blunt Support growth when treasury health is strong.
- Bailout backlash, treasury collapse, and failed redistribution can still drive the revolution.
- Counterplay should lean on relief, bargaining, and legitimacy restoration.

### Minarchism

- Heaviest local ignition from concentrated development and visible rent extraction.
- Strongest security, property-rights, and reintegration tools.
- Least forgiving environment for a sloppy revolutionary faction.
- The easiest regime to trigger locally, but the hardest regime to convert into a stable communist victory.

## Plot Panel UX

The Plot panel must be a first-class sidebar panel, not a hidden sub-modal.

### Panel Access

- Add `plot` to the sidebar menu stack with its own red-themed panel button.
- The panel opens from the same stack as Stability, Economy, Deals, Trade, and Lobbying.

### Panel Modes

The panel should render differently by player relationship to the plot.

1. Ineligible Player View
   - Shows hardship and instability summary only.
   - Explains why the plot is locked.
2. Eligible Founder View
   - Shows hardship triggers, founding button, and starter explanation.
3. Underground Member View
   - Shows Support, Heat, cell map, and hidden operations.
4. Public Revolutionary View
   - Shows Support, Supply, Heat, seized territory, operations, and victory progress.
5. Non-Communist Public View
   - Shows threat map, coalition tools, reintegration targets, and relief options.

### Recommended Tabs

1. Overview
2. Organization
3. Territories
4. Operations
5. Counterplay

### Required UI Content

Overview:

1. Current stage
2. Support, Supply, Heat
3. Victory countdown if active
4. Faction members and join pipeline

Organization:

1. Cell locations
2. Recruitable players
3. Hardship indicators
4. Defection and commitment status

Territories:

1. Seized properties
2. Entrenchment
3. Supply yield forecast
4. Reintegration threat

Operations:

1. Available actions
2. Costs and cooldowns
3. Region targeting
4. Recent successes and failures

Counterplay:

1. Coalition actions
2. Relief options
3. Security and blockade targets
4. Public legitimacy pressure

## Board Art And Seized Property Treatment

This is a hard requirement for the feature. Seized properties must look visually conquered, not merely highlighted.

### Asset Handling

- Move `/home/wnusair/Documents/Github/PoorUp/White_hammer_and_sickle.png` into the frontend asset pipeline.
- Rename it to something implementation-safe and explicit, recommended: `frontend/src/assets/plot/hammer-sickle-white.png`.

### Base Tile Rule

When a property is seized:

1. The entire square becomes red.
2. The standard property name presentation is removed.
3. The standard group color bar is removed.
4. The standard owner badge is removed.
5. A hammer-and-sickle overlay becomes the dominant identity.

This means the tile should no longer look like a normal property with a small status tag. It should look overwritten by a new regime.

### Single-Tile Rule

- If only one property tile is seized in a cluster, show a centered hammer-and-sickle icon only.
- Do not force the text `Property of the People` onto a single tile.
- This preserves clarity on small spaces.

### Multi-Tile Cluster Rule

If 2 or more directly adjacent properties are seized on the same board edge:

1. Keep each tile's background fully red.
2. Compute a shared overlay rect across the contiguous run.
3. Draw repeating white `Property of the People` text across the full cluster.
4. Repeat the hammer-and-sickle icon between text runs as needed to fill the space.
5. For side columns, rotate or orient the repeated text to match the geometry.

### Split Cluster Rule

- If seized properties are separated by non-seized tiles, corners, or retired spaces, they are not one cluster.
- Each contiguous cluster gets its own overlay treatment.
- If an individual tile inside a split area is large enough to fit text legibly, render the text inside that tile.
- If it is not large enough, render icon-only.

### Readability Rules

1. White text only.
2. Red background only.
3. No mixed color bars or old landlord labels.
4. Single tile: icon only.
5. Multi-tile cluster: repeated phrase and icons until the shared space is visually filled.
6. Narrow spaces degrade to icon-only rather than unreadable text.

### Implementation Direction

- Keep the per-tile red takeover state in `BoardSpace`.
- Add cluster overlay computation in `GameBoard` using already-calculated board-space rects.
- Do not attempt to fake cluster text inside individual tiles only. The real implementation should use board-level geometry.

## Backend State Model

Use Redis-backed `game_state` fields first. Do not require a SQL migration in v1 unless testing proves persistence gaps.

### Recommended State Additions

Under `game_state["social"]`:

```python
"plot": {
    "enabled": True,
    "public": False,
    "founder_id": None,
    "member_ids": [],
    "sympathizer_ids": [],
    "organizer_ids": [],
    "cadre_ids": [],
    "coalition_ids": [],
    "stage": "dormant",
    "support_pool": 0.0,
    "supply_pool": 0.0,
    "heat": 0,
    "control_percent": 0.0,
    "victory_countdown": None,
    "eligibility": {},
    "operations": [],
    "territories": {},
    "recent_failures": [],
}
```

Per player in serialized `players` state:

```python
"plot_role": "none" | "sympathizer" | "organizer" | "member" | "cadre",
"plot_join_round": None,
"plot_defection_cooldown_until": None,
"plot_hardship_score": 0,
"plot_support_contributed": 0.0,
"plot_supply_contributed": 0.0,
```

Per seized property in social property state:

```python
"plot_seized": True,
"plot_entrenchment": 0,
"plot_supply_yield": 0.0,
"plot_cluster_id": None,
"plot_contested": False,
"plot_blockaded": False,
"plot_last_levy_round": None,
```

## Backend Implementation Direction

### Social Engine

Primary anchor: `backend/app/engine/social.py`

Responsibilities:

1. Calculate hardship eligibility.
2. Maintain plot stage and faction state.
3. Convert social instability into plot-relevant pressure.
4. Mark legal seizure targets.
5. Compute per-property supply yield and cluster state.
6. Resolve entrenchment, blockades, reintegration pressure, and victory countdown.

### Win Logic

Primary anchor: `backend/app/engine/game_loop.py`

Responsibilities:

1. Keep current last-player-standing logic.
2. Add `check_plot_victory` alongside current winner logic.
3. Support a new winner payload type for faction wins.
4. Evaluate plot victory after round-end social resolution, not mid-animation or mid-action.

Recommended winner payload:

```python
{
    "type": "faction",
    "faction": "communist_plot",
    "member_ids": [..],
    "member_usernames": [..],
    "control_percent": 31.4,
    "victory_round": 12,
}
```

### Landings And Property Interactions

Primary anchor: `backend/app/engine/events.py`

Responsibilities:

1. Route seized-property landings through solidarity levy logic, not standard rent.
2. Exempt communist members from the levy.
3. Respect blockades, entrenchment, and temporary passage effects.
4. Preserve existing unionized-property handling where possible, but bound the new levy logic so it does not become abusive.

### Socket Actions

Primary anchor: `backend/app/sockets/game_events.py`

Add new server-validated events:

1. `plot_start`
2. `plot_action`
3. `plot_join`
4. `plot_leave`
5. `plot_counter_action`

`plot_action` should accept a typed payload rather than one event per tiny action.

Recommended action types:

1. `mutual_aid`
2. `seed_cell`
3. `recruit`
4. `agitate`
5. `sabotage`
6. `attempt_seizure`
7. `fortify`
8. `regional_council`
9. `defend_reintegration`

### Bots

Primary anchor: `backend/app/engine/bots.py`

Bots must be able to play for or against the system with real planning.

Add `plot_doctrine` or equivalent bot weighting:

1. `none`
2. `opportunist_revolutionary`
3. `vanguardist`
4. `syndicalist`
5. `reactionary_coalitionist`

Required bot behavior:

1. Recognize hardship eligibility and decide whether to found the plot.
2. Evaluate whether joining is worth shared victory.
3. Plan 2 to 3 rounds ahead on seizures and defenses.
4. Form coalitions automatically when plot control becomes threatening.
5. Spend on relief if repression alone would backfire.

## Frontend Implementation Direction

### State Normalization

Primary anchors:

1. `frontend/src/utils/gameState.js`
2. `frontend/src/hooks/useSocket.js`
3. `frontend/src/hooks/useGameState.js`

Responsibilities:

1. Normalize `social.plot` into a stable UI contract.
2. Merge seized-property state into normalized properties.
3. Surface plot-specific per-property data like entrenchment and supply yield.
4. Handle faction-style `game_over` payloads.

### Modal And Panel Mounting

Primary anchors:

1. `frontend/src/components/Game/SidebarMenuStack.jsx`
2. `frontend/src/components/Game/GameLayout.jsx`

Responsibilities:

1. Register the Plot panel button.
2. Mount a `PlotPanelModal` or equivalent.
3. Ensure the panel can render both revolutionary and counter-revolution states.

### Board Rendering

Primary anchors:

1. `frontend/src/components/Board/BoardSpace.jsx`
2. `frontend/src/components/Board/GameBoard.jsx`

Responsibilities:

1. Replace current light revolutionary indicator styling with full seizure takeover visuals.
2. Hide old name/group-color presentation for seized tiles.
3. Compute contiguous cluster overlay rects on the board.
4. Render repeated `Property of the People` text and hammer-and-sickle overlays only where geometry supports them.
5. Fall back to icon-only on single or unreadably small spaces.

### Game Over Presentation

Primary anchor: `frontend/src/components/Modals/GameOverModal.jsx`

Responsibilities:

1. Support faction winners.
2. Display all committed communist winners together.
3. Use faction-specific copy and red-accented presentation.
4. Preserve ordinary player-ranking tables underneath.

## Safety Rails

These rails are required to keep the plot viable but not dominant.

1. No founding before round 4.
2. No first seizure before round 6.
3. No victory check before round 9.
4. Maximum one stage advance per round.
5. Maximum one seizure attempt per round before Dual Power.
6. Bounded solidarity levies instead of extreme union-rent multipliers.
7. Heat blocks victory if the faction grows too recklessly.
8. Support decays if the faction stops doing political work and becomes only a land holder.
9. Coalition repression backfires in distressed regions.
10. Defection is costly, but allowed, so shared victory is meaningful and not free.

## Scope Boundary For V1

Included in v1:

1. Plot panel.
2. Founding and joining flow.
3. Support, Supply, and Heat.
4. Seized-property logic.
5. Shared faction victory.
6. Anti-revolution coalition play.
7. Board red takeover art and cluster text/icon overlays.
8. Bot participation on both sides.

Not required in v1:

1. A separate SQL schema for permanent faction history.
2. Multiple competing revolutionary factions.
3. New board spaces dedicated only to the plot path.
4. A fully separate tutorial flow beyond panel help text.

## Implementation Order

1. Backend plot state, eligibility, and round-end resolution.
2. Shared faction winner contract.
3. Socket actions and server validation.
4. Frontend normalization and Plot panel shell.
5. Seized-property board visuals and cluster overlay renderer.
6. Bot founding, joining, and coalition logic.
7. Balance pass across liberal democracy, social democracy, and minarchism.

## Verification Targets

### Backend

1. `.venv/bin/python backend/tests/test_social.py`
2. `.venv/bin/python backend/tests/test_game_loop.py`
3. `.venv/bin/python backend/tests/test_events.py`
4. `.venv/bin/python backend/tests/test_bots.py`

### Frontend

1. `npm test` in `frontend/`
2. Add Plot panel tests patterned after the current Stability panel tests.
3. Add board overlay tests for single-tile, contiguous-cluster, and split-cluster seized states.

### Manual Playtest Matrix

1. A struggling solo founder fails because they expand too early and get crushed.
2. A disciplined solo founder can still survive the countdown and win without recruiting a second committed member.
3. Two unlucky players successfully build a faction and share the win after surviving the countdown.
4. Wealthier players form a coalition, use relief plus reintegration, and stop the revolution without brute-force abuse.
5. Minarchism produces faster ignition around overdeveloped landlord clusters, but still punishes sloppy revolutionary overreach.

## Final Design Intention

The communist plot should feel like a dramatic second game hidden inside the main game, but not a replacement for it.

It exists to answer a specific problem: players who get unlucky early should have a viable, skillful path back into relevance. The answer should not be free money, free land, or a random uprising that hands them the match. The answer should be a disciplined political arc with real costs, real coordination, real visibility, and real enemies.

If this system is implemented correctly:

1. Early losers get a meaningful comeback line.
2. Winners and frontrunners get a new kind of threat to manage.
3. Seized territory becomes one of the clearest visual states on the board.
4. The game gains a new late-midgame drama without losing its economic-strategy core.