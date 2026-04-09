# Liberal Democracy Overhaul Spec

## Goal

Rebuild liberal democracy so it plays like a western capitalist regime instead of a weaker social democracy. The mode should feel distinct through capital markets, investor confidence, private-equity upside, and government policy asymmetry rather than by simply lowering welfare.

## Design Pillars

1. Capital markets are a core system, not flavor text.
2. Liberal democracy rewards liquid capital and investor contracts more than other regimes.
3. Welfare and tax policy still matter, but they are not the regime's main identity.
4. Bailouts and deregulation improve short-term capitalist flexibility while risking confidence and social stability.
5. Safety rails stay moderate so the mode does not become an unchecked runaway economy.

## Implemented In This Slice

### Backend

- Liberal democracy now initializes with:
  - higher baseline stability than social democracy
  - moderate welfare instead of pseudo-social-democratic welfare drift
  - bailouts enabled by default
  - market confidence as a tracked economy metric
  - derived capital-yield and private-equity bonus values

- The economy engine now derives and normalizes liberal-democracy-only state:
  - `market_confidence`
  - `capital_yield_rate`
  - `capital_yield_cap_per_player`
  - `capital_yield_reserve_floor`
  - `capital_yield_last_round`
  - `private_equity_bonus_multiplier`

- Liberal democracy now gets a round-start capital yield payout for players holding liquid cash above a reserve floor.

- Economic drift now differentiates liberal democracy more sharply:
  - welfare mean-reverts toward a moderate center
  - market confidence responds to inflation, inequality, taxes, treasury health, and bailout posture
  - private-equity bonus and capital yield are re-derived from the current macro state

- Bailouts under liberal democracy now reduce market confidence.

- Private-equity investment tranches get a liberal-democracy bonus multiplier tied to market conditions.

### Social Pressure

- Liberal democracy now generates a distinct `shareholder_pressure` grievance instead of only reusing generic welfare or oligarchy backlash.

- Shareholder pressure rises when:
  - market confidence, capital yield, and private-equity bonuses are all strong
  - hardship and inequality stay visible underneath that market optimism
  - owners keep pushing `market_deregulation` from a concentrated position

- This backlash now feeds property tension, dominant grievances, and recommended remedies, so liberal democracy can produce gentrification-style unrest and market-discontent flashpoints.

- `market_deregulation` is now treated as a hostile lobbying target in the social engine when wealthy owners use it against a stressed table.

### Bots

- Bots now derive liberal-democracy-specific regime metrics:
  - market confidence
  - capital-yield capture score
  - private-equity edge score
  - market-overheat score

- A new `capital_markets_arbitrage` doctrine lets bots:
  - preserve cash to harvest capital yield when the market climate is good
  - treat private-equity bridges as more attractive under liberal democracy
  - use the capital-markets lobbying axis to either restore investor confidence or cool shareholder backlash

- Bot purchase, development, unmortgage, and deal-proposal heuristics now react to liberal-democracy market conditions instead of spending cash as if all liquidity were equivalent.

### Lobbying

- Lobbying definitions now support government-specific availability and cost/effect modifiers.

- Liberal democracy now has a dedicated `capital_markets` axis:
  - `market_deregulation`
  - `capital_controls`

- Existing axes also behave differently under liberal democracy:
  - tax relief is cheaper and slightly stronger
  - welfare expansion is more expensive and slightly weaker
  - housing deregulation is somewhat cheaper and stronger

- The backend rejects lobbying targets that do not belong to the active government.

### Frontend

- Liberal democracy copy now describes the regime as capital-markets-first.

- Normalized economy state now carries the new market metrics.

- The economy dashboard now shows market confidence and capital yield under liberal democracy.

- The lobbying modal now shows a liberal-democracy-only capital-markets axis.

- The economy details modal now surfaces market confidence, capital yield, and the private-equity bonus when liberal democracy is active.

- The deal desk now explains the current liberal-democracy market climate and shows the effective payout ceiling on PE clauses after the active bonus multiplier is applied.

- The property modal now shows the same PE climate and effective investor ceilings on active investment-backed build options and ongoing obligations.

## Safety Rails

1. Capital yield only pays on cash above a reserve floor.
2. Capital yield is capped per player each round.
3. Private-equity bonus is bounded instead of open-ended.
4. Market confidence falls when bailouts, inflation, inequality, taxes, or overextended welfare start dragging the regime away from its capitalist center.

## Next Implementation Steps

1. Add more incident text and event-card flavor for shareholder pressure so protests feel less generic in the log.
2. Extend bot trade logic so bots also invest outward as the financier, not just as the recipient of PE bridges.
3. Add frontend coverage for the liberal-democracy lobbying axis and economy widgets beyond the PE surfaces.
4. Playtest bailout confidence loss, capital-yield caps, and capital-controls tuning against social democracy to keep the regimes distinct without making liberal democracy dominant.

## Verification Targets

1. `.venv/bin/python backend/tests/test_economy.py`
2. `.venv/bin/python backend/tests/test_game_loop.py`
3. `.venv/bin/python backend/tests/test_social.py`
4. `.venv/bin/python backend/tests/test_bots.py`
5. `npm test` in `frontend/`