import { useEffect, useMemo, useState } from 'react';

const DIFFICULTY_STYLES = {
  easy: 'border-emerald-700/70 bg-emerald-950/40 text-emerald-200',
  normal: 'border-sky-700/70 bg-sky-950/40 text-sky-200',
  hard: 'border-amber-700/70 bg-amber-950/40 text-amber-200',
  expert: 'border-rose-700/70 bg-rose-950/40 text-rose-200',
};

function difficultyStyle(key) {
  return DIFFICULTY_STYLES[key] || 'border-gray-700 bg-gray-900 text-gray-200';
}

function ArchetypeSummary({ archetype }) {
  if (!archetype) {
    return (
      <div className="rounded-2xl border border-gray-800 bg-gray-950/70 p-4 text-sm text-gray-400">
        Select an archetype to preview its behavior.
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-gray-800 bg-gray-950/70 p-4 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.28em] text-gray-500">Archetype</p>
          <h3 className="mt-1 text-lg font-semibold text-white">{archetype.label}</h3>
        </div>
        <div className="flex flex-wrap justify-end gap-1.5">
          {['easy', 'normal', 'hard', 'expert'].map((difficulty) => (
            <span
              key={`${archetype.key}-${difficulty}`}
              className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-wide ${difficultyStyle(difficulty)}`}
            >
              {difficulty}
            </span>
          ))}
        </div>
      </div>
      <p className="text-sm leading-6 text-gray-300">{archetype.short_description}</p>
      <div>
        <p className="text-[11px] uppercase tracking-[0.24em] text-gray-500">Example Behaviors</p>
        <div className="mt-2 space-y-2">
          {(archetype.example_behaviors || []).map((behavior) => (
            <p key={behavior} className="text-sm text-gray-300">{behavior}</p>
          ))}
        </div>
      </div>
      <div>
        <p className="text-[11px] uppercase tracking-[0.24em] text-gray-500">Preferred Doctrines</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {(archetype.preferred_doctrines || []).map((doctrine) => (
            <span
              key={`${archetype.key}-${doctrine}`}
              className="rounded-full border border-cyan-900/80 bg-cyan-950/30 px-2 py-1 text-[11px] font-semibold text-cyan-200"
            >
              {doctrine.replace(/_/g, ' ')}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function DifficultyPicker({ difficulties, value, onChange }) {
  return (
    <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
      {difficulties.map((difficulty) => {
        const selected = difficulty.key === value;
        return (
          <button
            key={difficulty.key}
            type="button"
            onClick={() => onChange(difficulty.key)}
            className={[
              'rounded-2xl border p-3 text-left transition',
              selected
                ? difficultyStyle(difficulty.key)
                : 'border-gray-800 bg-gray-950/50 text-gray-300 hover:border-gray-700',
            ].join(' ')}
          >
            <p className="text-sm font-semibold">{difficulty.label}</p>
            <p className="mt-1 text-xs leading-5 text-gray-400">{difficulty.summary}</p>
          </button>
        );
      })}
    </div>
  );
}

export default function BotSetupModal({
  isOpen,
  onClose,
  botSetup,
  bots,
  openSeats,
  onAddBots,
  onUpdateBot,
  onRemoveBot,
  error,
}) {
  const difficulties = botSetup?.difficulties || [];
  const archetypes = botSetup?.archetypes || botSetup?.personalities || [];
  const defaultDifficulty = botSetup?.defaults?.difficulty || difficulties[1]?.key || difficulties[0]?.key || 'normal';
  const defaultArchetype = botSetup?.defaults?.archetype_by_difficulty?.[defaultDifficulty]
    || botSetup?.defaults?.personality_by_difficulty?.[defaultDifficulty]
    || archetypes[0]?.key
    || '';

  const [count, setCount] = useState(1);
  const [difficulty, setDifficulty] = useState(defaultDifficulty);
  const [archetype, setArchetype] = useState(defaultArchetype);
  const [submitting, setSubmitting] = useState(false);
  const [updatingPlayerId, setUpdatingPlayerId] = useState(null);
  const [removingPlayerId, setRemovingPlayerId] = useState(null);

  const availableArchetypes = useMemo(() => archetypes, [archetypes]);
  const selectedQuickArchetype = useMemo(
    () => availableArchetypes.find((entry) => entry.key === archetype) || availableArchetypes[0] || null,
    [archetype, availableArchetypes],
  );

  useEffect(() => {
    if (!availableArchetypes.length) {
      setArchetype('');
      return;
    }
    if (!availableArchetypes.some((entry) => entry.key === archetype)) {
      setArchetype(availableArchetypes[0].key);
    }
  }, [archetype, availableArchetypes]);

  useEffect(() => {
    if (!isOpen) {
      setSubmitting(false);
      setUpdatingPlayerId(null);
      setRemovingPlayerId(null);
    }
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  const handleAddBots = async () => {
    if (!selectedQuickArchetype || openSeats <= 0) {
      return;
    }
    setSubmitting(true);
    try {
      await onAddBots({
        count: Math.max(1, Math.min(openSeats, count)),
        difficulty,
        archetype: selectedQuickArchetype.key,
      });
      setCount(1);
    } finally {
      setSubmitting(false);
    }
  };

  const updateBotDifficulty = async (bot, nextDifficulty) => {
    setUpdatingPlayerId(bot.id);
    try {
      await onUpdateBot(bot.id, {
        difficulty: nextDifficulty,
        archetype: bot.bot_archetype || selectedQuickArchetype?.key || availableArchetypes[0]?.key,
      });
    } finally {
      setUpdatingPlayerId(null);
    }
  };

  const updateBotArchetype = async (bot, nextArchetype) => {
    setUpdatingPlayerId(bot.id);
    try {
      await onUpdateBot(bot.id, { difficulty: bot.bot_difficulty, archetype: nextArchetype });
    } finally {
      setUpdatingPlayerId(null);
    }
  };

  const removeBot = async (botId) => {
    setRemovingPlayerId(botId);
    try {
      await onRemoveBot(botId);
    } finally {
      setRemovingPlayerId(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="w-full max-w-7xl max-h-[calc(100vh-2rem)] overflow-hidden rounded-3xl border border-gray-800 bg-gray-950 shadow-2xl flex flex-col">
        <div className="flex items-start justify-between gap-4 border-b border-gray-800 px-6 py-5">
          <div>
            <p className="text-xs uppercase tracking-[0.32em] text-cyan-400">Bot Setup</p>
            <h2 className="mt-2 text-2xl font-bold text-white">Per-bot difficulty and archetype</h2>
            <p className="mt-1 text-sm text-gray-400">
              Pick a government-style archetype, then let difficulty control foresight and risk appetite.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-gray-700 bg-gray-900 px-4 py-2 text-sm font-semibold text-gray-200 transition hover:border-gray-600 hover:text-white"
          >
            Close
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">
          <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
            <div className="rounded-3xl border border-gray-800 bg-gray-950/80 p-5 space-y-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-white">Quick Add</p>
                  <p className="mt-1 text-xs text-gray-400">Choose a difficulty, then pick the archetype you want in the lobby.</p>
                </div>
                <span className="rounded-full border border-gray-700 bg-gray-900 px-3 py-1 text-xs font-semibold text-gray-300">
                  {openSeats} open seat{openSeats === 1 ? '' : 's'}
                </span>
              </div>

              <div>
                <p className="text-[11px] uppercase tracking-[0.24em] text-gray-500">Difficulty</p>
                <div className="mt-3">
                  <DifficultyPicker
                    difficulties={difficulties}
                    value={difficulty}
                    onChange={setDifficulty}
                  />
                </div>
              </div>

              <div className="grid gap-4 lg:grid-cols-[0.62fr_0.38fr]">
                <div className="space-y-4">
                  <div>
                    <label className="block text-[11px] uppercase tracking-[0.24em] text-gray-500">Bot Count</label>
                    <div className="mt-2 flex items-center gap-3">
                      <button
                        type="button"
                        onClick={() => setCount((current) => Math.max(1, current - 1))}
                        className="rounded-xl border border-gray-700 bg-gray-900 px-3 py-2 text-sm font-semibold text-gray-200 transition hover:border-gray-600"
                      >
                        -
                      </button>
                      <input
                        type="number"
                        min={1}
                        max={Math.max(1, openSeats)}
                        value={count}
                        onChange={(event) => setCount(Math.max(1, Math.min(openSeats || 1, Number(event.target.value) || 1)))}
                        className="w-24 rounded-xl border border-gray-700 bg-gray-900 px-3 py-2 text-center text-white focus:border-cyan-500 focus:outline-none"
                      />
                      <button
                        type="button"
                        onClick={() => setCount((current) => Math.min(Math.max(1, openSeats), current + 1))}
                        className="rounded-xl border border-gray-700 bg-gray-900 px-3 py-2 text-sm font-semibold text-gray-200 transition hover:border-gray-600"
                      >
                        +
                      </button>
                    </div>
                  </div>

                  <div>
                    <label className="block text-[11px] uppercase tracking-[0.24em] text-gray-500">Archetype</label>
                    <select
                      value={selectedQuickArchetype?.key || ''}
                      onChange={(event) => setArchetype(event.target.value)}
                      className="mt-2 w-full rounded-2xl border border-gray-700 bg-gray-900 px-4 py-3 text-sm text-white focus:border-cyan-500 focus:outline-none"
                    >
                      {availableArchetypes.map((entry) => (
                        <option key={entry.key} value={entry.key}>{entry.label}</option>
                      ))}
                    </select>
                  </div>

                  <button
                    type="button"
                    onClick={handleAddBots}
                    disabled={submitting || !selectedQuickArchetype || openSeats <= 0}
                    className="w-full rounded-2xl bg-cyan-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:bg-gray-800 disabled:text-gray-500"
                  >
                    {submitting ? 'Adding bots…' : 'Add Bots'}
                  </button>
                </div>

                <ArchetypeSummary archetype={selectedQuickArchetype} />
              </div>
            </div>

            <div className="rounded-3xl border border-gray-800 bg-gray-950/80 p-5 space-y-4">
              <div>
                <p className="text-sm font-semibold text-white">Manage Existing Bots</p>
                <p className="mt-1 text-xs text-gray-400">Adjust difficulty and archetype per bot without removing them from the lobby.</p>
              </div>

              {error && (
                <div className="rounded-2xl border border-rose-900/70 bg-rose-950/30 px-4 py-3 text-sm text-rose-200">
                  {error}
                </div>
              )}

              {bots.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-gray-800 bg-gray-950/50 px-4 py-5 text-sm text-gray-500">
                  No bots in this lobby yet.
                </div>
              ) : (
                <div className="space-y-3">
                  {bots.map((bot) => {
                    const selectedBotArchetype = availableArchetypes.find((entry) => (
                      entry.key === bot.bot_archetype
                      || entry.key === bot.bot_persona
                    )) || availableArchetypes[0] || null;
                    const selectedBotArchetypeKey = selectedBotArchetype?.key || '';
                    const rowBusy = updatingPlayerId === bot.id || removingPlayerId === bot.id;

                    return (
                      <div key={bot.id} className="rounded-2xl border border-gray-800 bg-gray-950/70 p-4 space-y-3">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold text-white">{bot.username}</p>
                            <p className="text-xs text-gray-500">Doctrine: {bot.bot_doctrine?.replace(/_/g, ' ')}</p>
                          </div>
                          <button
                            type="button"
                            onClick={() => removeBot(bot.id)}
                            disabled={rowBusy}
                            className="rounded-xl border border-rose-900/70 bg-rose-950/30 px-3 py-2 text-xs font-semibold text-rose-200 transition hover:border-rose-700 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            {removingPlayerId === bot.id ? 'Removing…' : 'Remove'}
                          </button>
                        </div>

                        <div className="grid gap-3 sm:grid-cols-2">
                          <label className="text-xs text-gray-400">
                            Difficulty
                            <select
                              value={bot.bot_difficulty}
                              disabled={rowBusy}
                              onChange={(event) => updateBotDifficulty(bot, event.target.value)}
                              className="mt-2 w-full rounded-xl border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white focus:border-cyan-500 focus:outline-none"
                            >
                              {difficulties.map((entry) => (
                                <option key={`${bot.id}-${entry.key}`} value={entry.key}>{entry.label}</option>
                              ))}
                            </select>
                          </label>
                          <label className="text-xs text-gray-400">
                            Archetype
                            <select
                              value={selectedBotArchetypeKey}
                              disabled={rowBusy}
                              onChange={(event) => updateBotArchetype(bot, event.target.value)}
                              className="mt-2 w-full rounded-xl border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white focus:border-cyan-500 focus:outline-none"
                            >
                              {availableArchetypes.map((entry) => (
                                <option key={`${bot.id}-${entry.key}`} value={entry.key}>{entry.label}</option>
                              ))}
                            </select>
                          </label>
                        </div>

                        <div className="rounded-2xl border border-gray-800 bg-gray-900/70 p-3 space-y-2">
                          <div className="flex flex-wrap gap-2">
                            <span className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-wide ${difficultyStyle(bot.bot_difficulty)}`}>
                              {bot.bot_difficulty_label || bot.bot_difficulty}
                            </span>
                            <span className="rounded-full border border-indigo-900/70 bg-indigo-950/30 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-indigo-200">
                              {selectedBotArchetype?.label || bot.bot_archetype_label || bot.bot_archetype}
                            </span>
                          </div>
                          <p className="text-sm text-gray-300">
                            {selectedBotArchetype?.short_description || bot.bot_archetype_description || bot.bot_persona_description}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
