import { GOVERNMENT_TYPES, GAME_MODES } from '../../utils/constants';

const DEFAULT_SETTINGS = {
  starting_money: 1500,
  go_salary: 200,
  turn_timer_enabled: true,
  turn_time_limit_seconds: 90,
  property_tax_every_n_rounds: 5,
  hyper_inflation_round: 50,
  max_players: 6,
  government_type: 'liberal_democracy',
  game_mode: 'standard',
  auction_enabled: true,
  trading_enabled: true,
  lobbying_enabled: true,
  deals_enabled: true,
  private_equity_enabled: true,
  max_active_deals_per_player: 3,
  max_rent_discount_percent: 90,
  max_private_equity_payout_multiple: 1.75,
  tax_every_turn: false,
  income_tax_on_pass_go: true,
  welfare_system_enabled: true,
  welfare_balance_cap: 0,
  collect_rent_while_jailed: false,
  free_parking_pot_enabled: false,
  double_on_go: false,
};

export default function SettingsPanel({ settings = {}, onChange, readOnly = false }) {
  const merged = { ...DEFAULT_SETTINGS, ...settings };

  const handleChange = (key, value) => {
    if (readOnly) return;
    onChange({ ...merged, [key]: value });
  };

  const Toggle = ({ label, settingKey, description }) => (
    <label className="flex items-start gap-3 cursor-pointer group">
      <div className="relative mt-0.5">
        <input
          type="checkbox"
          checked={!!merged[settingKey]}
          onChange={(e) => handleChange(settingKey, e.target.checked)}
          disabled={readOnly}
          className="sr-only"
        />
        <div
          className={[
            'w-10 h-5 rounded-full transition-colors cursor-pointer',
            merged[settingKey] ? 'bg-blue-600' : 'bg-gray-600',
            readOnly ? 'cursor-not-allowed' : '',
          ].join(' ')}
        >
          <div
            className={[
              'w-4 h-4 rounded-full bg-white mt-0.5 transition-transform shadow',
              merged[settingKey] ? 'translate-x-5' : 'translate-x-0.5',
            ].join(' ')}
          />
        </div>
      </div>
      <div>
        <span className="text-sm font-medium text-gray-200">{label}</span>
        {description && <p className="text-xs text-gray-500 mt-0.5">{description}</p>}
      </div>
    </label>
  );

  const NumberInput = ({ label, settingKey, min = 0, max, step = 1, disabled = false, helperText = '' }) => (
    <div>
      <label className="block text-sm font-medium text-gray-300 mb-1">{label}</label>
      <input
        type="number"
        value={merged[settingKey]}
        min={min}
        max={max}
        step={step}
        disabled={readOnly || disabled}
        onChange={(e) => handleChange(settingKey, Number(e.target.value))}
        className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-white text-sm
                   focus:outline-none focus:border-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
      />
      {helperText && <p className="text-xs text-gray-500 mt-1">{helperText}</p>}
    </div>
  );

  return (
    <div className="space-y-6">
      {readOnly && (
        <p className="text-xs text-gray-500 italic">Only the host can change settings.</p>
      )}

      {/* Numeric settings */}
      <div>
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">Economy</h3>
        <div className="grid grid-cols-2 gap-3">
          <NumberInput label="Starting Money ($)" settingKey="starting_money" min={500} max={10000} step={100} />
          <NumberInput label="GO Salary ($)" settingKey="go_salary" min={100} max={1000} step={50} />
          <div className="space-y-3">
            <Toggle
              label="Turn Timer"
              settingKey="turn_timer_enabled"
              description="Disable this to remove per-turn time limits from the game UI"
            />
            <NumberInput
              label="Turn Time Limit (sec)"
              settingKey="turn_time_limit_seconds"
              min={15}
              max={300}
              disabled={!merged.turn_timer_enabled}
              helperText={merged.turn_timer_enabled ? '' : 'Enable the turn timer to edit the limit.'}
            />
          </div>
          <NumberInput label="Hyper-Inflation Round" settingKey="hyper_inflation_round" min={5} max={50} />
          <NumberInput label="Max Players" settingKey="max_players" min={2} max={10} />
        </div>
      </div>

      {/* Government type */}
      <div>
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">Government</h3>
        <div className="space-y-2">
          {Object.entries(GOVERNMENT_TYPES).map(([key, { label, description }]) => (
            <label
              key={key}
              className={[
                'flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition',
                merged.government_type === key
                  ? 'border-blue-500 bg-blue-900/20'
                  : 'border-gray-600 bg-gray-800 hover:border-gray-500',
                readOnly ? 'cursor-not-allowed' : '',
              ].join(' ')}
            >
              <input
                type="radio"
                name="government_type"
                value={key}
                checked={merged.government_type === key}
                disabled={readOnly}
                onChange={() => handleChange('government_type', key)}
                className="mt-1 accent-blue-500"
              />
              <div>
                <span className="text-sm font-medium text-white">{label}</span>
                <p className="text-xs text-gray-400 mt-0.5">{description}</p>
              </div>
            </label>
          ))}
        </div>
      </div>

      {/* Game mode */}
      <div>
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">Game Mode</h3>
        <div className="grid grid-cols-2 gap-2">
          {Object.entries(GAME_MODES).map(([key, { label, description }]) => (
            <label
              key={key}
              className={[
                'flex flex-col gap-1 p-3 rounded-lg border cursor-pointer transition',
                merged.game_mode === key
                  ? 'border-purple-500 bg-purple-900/20'
                  : 'border-gray-600 bg-gray-800 hover:border-gray-500',
                readOnly ? 'cursor-not-allowed' : '',
              ].join(' ')}
            >
              <div className="flex items-center gap-2">
                <input
                  type="radio"
                  name="game_mode"
                  value={key}
                  checked={merged.game_mode === key}
                  disabled={readOnly}
                  onChange={() => handleChange('game_mode', key)}
                  className="accent-purple-500"
                />
                <span className="text-sm font-medium text-white">{label}</span>
              </div>
              <p className="text-xs text-gray-400 ml-5">{description}</p>
            </label>
          ))}
        </div>
      </div>

      {/* Feature toggles */}
      <div>
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">Features</h3>
        <div className="space-y-3">
          <Toggle label="Allow Auctions" settingKey="auction_enabled" description="Properties go to auction when declined" />
          <Toggle label="Allow Trading" settingKey="trading_enabled" description="Players can trade properties" />
          <Toggle label="Allow Lobbying" settingKey="lobbying_enabled" description="Players can lobby for policy changes" />
          <Toggle label="Allow Deals" settingKey="deals_enabled" description="Players can negotiate temporary protections and funding contracts" />
          <Toggle label="Allow Private Equity" settingKey="private_equity_enabled" description="Development investment clauses can fund builds through escrow" />
          <Toggle label="Collect Rent In Jail" settingKey="collect_rent_while_jailed" description="By default jailed owners do not collect rent. Turn this on to allow prison rent." />
          <Toggle label="Free Parking Jackpot" settingKey="free_parking_pot_enabled" description="Tax money pools at Free Parking" />
          <Toggle label="Double GO Salary" settingKey="double_on_go" description="Double GO salary is applied when enabled" />
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">Deals</h3>
        <div className="grid grid-cols-2 gap-3">
          <NumberInput label="Max Active Deals Per Player" settingKey="max_active_deals_per_player" min={1} max={6} />
          <NumberInput label="Max Rent Discount (%)" settingKey="max_rent_discount_percent" min={10} max={90} step={5} />
          <NumberInput label="Max PE Payout Multiple" settingKey="max_private_equity_payout_multiple" min={1} max={3} step={0.05} />
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">Taxation & Welfare</h3>
        <p className="text-xs text-gray-500 mb-3">
          Welfare is percentage-based. Qualifying players receive a share of the gap between their balance and $200 above the welfare cap. A cap of $0 uses a $400 target instead.
        </p>
        <div className="grid grid-cols-2 gap-3 mb-4">
          <NumberInput label="Welfare Balance Cap ($)" settingKey="welfare_balance_cap" min={0} max={10000} step={50} />
          <NumberInput label="Property Tax Every N Rounds" settingKey="property_tax_every_n_rounds" min={1} max={20} />
        </div>
        <div className="space-y-3">
          <Toggle label="Welfare System" settingKey="welfare_system_enabled" description="Pay eligible players at the start of each round when the treasury can afford it" />
          <Toggle label="Income Tax on Pass GO" settingKey="income_tax_on_pass_go" description="Collect GO salary, then charge the current percentage-based income tax on cash" />
          <Toggle label="Turn Tax" settingKey="tax_every_turn" description="Charge every player a small percentage-based tax at the end of each turn" />
        </div>
      </div>
    </div>
  );
}
