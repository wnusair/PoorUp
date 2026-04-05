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

function PersonalitySummary({ personality }) {
  if (!personality) {
    return (
      <div className="rounded-2xl border border-gray-800 bg-gray-950/70 p-4 text-sm text-gray-400">
        Select a personality to preview its doctrine and behavior.
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-gray-800 bg-gray-950/70 p-4 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.28em] text-gray-500">Profile</p>
          <h3 className="mt-1 text-lg font-semibold text-white">{personality.label}</h3>
        </div>
        <div className="flex flex-wrap justify-end gap-1.5">
          {personality.allowed_difficulties.map((difficulty) => (
            <span
              key={`${personality.key}-${difficulty}`}
              className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-wide ${difficultyStyle(difficulty)}`}
            >
              {difficulty}
            </span>
          ))}
        </div>
      </div>
      <p className="text-sm leading-6 text-gray-300">{personality.short_description}</p>
      <div>
        <p className="text-[11px] uppercase tracking-[0.24em] text-gray-500">Example Behaviors</p>
        <div className="mt-2 space-y-2">
          {personality.example_behaviors.map((behavior) => (
            <p key={behavior} className="text-sm text-gray-300">{behavior}</p>
          ))}
        </div>
      </div>
      <div>
        <p className="text-[11px] uppercase tracking-[0.24em] text-gray-500">Preferred Doctrines</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {personality.preferred_doctrines.map((doctrine) => (
            <span
              key={`${personality.key}-${doctrine}`}
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
  const personalities = botSetup?.personalities || [];
  const defaultDifficulty = botSetup?.defaults?.difficulty || difficulties[1]?.key || difficulties[0]?.key || 'normal';

  const [count, setCount] = useState(1);
  const [difficulty, setDifficulty] = useState(defaultDifficulty);
  const [persona, setPersona] = useState(botSetup?.defaults?.personality_by_difficulty?.[defaultDifficulty] || '');
  const [submitting, setSubmitting] = useState(false);
  const [updatingPlayerId, setUpdatingPlayerId] = useState(null);
  const [removingPlayerId, setRemovingPlayerId] = useState(null);

  const personalitiesByDifficulty = useMemo(() => {
    const byDifficulty = {};
    personalities.forEach((entry) => {
      entry.allowed_difficulties.forEach((allowedDifficulty) => {
        byDifficulty[allowedDifficulty] = [...(byDifficulty[allowedDifficulty] || []), entry];
      });
    });
    return byDifficulty;
  }, [personalities]);

  const availablePersonalities = useMemo(
    () => personalitiesByDifficulty[difficulty] || [],
    [difficulty, personalitiesByDifficulty],
  );

  const selectedQuickPersonality = useMemo(
    () => availablePersonalities.find((entry) => entry.key === persona) || availablePersonalities[0] || null,
    [availablePersonalities, persona],
  );

  useEffect(() => {
    if (!availablePersonalities.length) {
      setPersona('');
      return;
    }
    if (!availablePersonalities.some((entry) => entry.key === persona)) {
      setPersona(availablePersonalities[0].key);
    }
  }, [availablePersonalities, persona]);

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
    if (!selectedQuickPersonality || openSeats <= 0) {
      return;
    }
    setSubmitting(true);
    try {
      await onAddBots({
        count: Math.max(1, Math.min(openSeats, count)),
        difficulty,
        persona: selectedQuickPersonality.key,
      });
      setCount(1);
    } finally {
      setSubmitting(false);
    }
  };

  const updateBotDifficulty = async (bot, nextDifficulty) => {
    const compatiblePersonalities = personalitiesByDifficulty[nextDifficulty] || [];
    const nextPersona = compatiblePersonalities.some((entry) => entry.key === bot.bot_persona)
      ? bot.bot_persona
      : compatiblePersonalities[0]?.key;
    if (!nextPersona) {
      return;
    }
    setUpdatingPlayerId(bot.id);
    try {
      await onUpdateBot(bot.id, { difficulty: nextDifficulty, persona: nextPersona });
    } finally {
      setUpdatingPlayerId(null);
    }
  };

  const updateBotPersona = async (bot, nextPersona) => {
    setUpdatingPlayerId(bot.id);
    try {
      await onUpdateBot(bot.id, { difficulty: bot.bot_difficulty, persona: nextPersona });
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
      <div className="w-full max-w-5xl max-h-[calc(100vh-2rem)] overflow-hidden rounded-3xl border border-gray-800 bg-gray-950 shadow-2xl flex flex-col">
        <div className="flex items-start justify-between gap-4 border-b border-gray-800 px-6 py-5">
          <div>
            <p className="text-xs uppercase tracking-[0.32em] text-cyan-400">Bot Setup</p>
            <h2 className="mt-2 text-2xl font-bold text-white">Per-bot difficulty and personality</h2>
            <p className="mt-1 text-sm text-gray-400">
              Quick-add a configured bot batch, then refine individual bots inline without touching the main settings column.
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
                  <p className="mt-1 text-xs text-gray-400">Choose a difficulty, then pick a compatible personality profile.</p>
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
                    <label className="block text-[11px] uppercase tracking-[0.24em] text-gray-500">Personality</label>
                    <select
                      value={selectedQuickPersonality?.key || ''}
                      onChange={(event) => setPersona(event.target.value)}
                      className="mt-2 w-full rounded-2xl border border-gray-700 bg-gray-900 px-4 py-3 text-sm text-white focus:border-cyan-500 focus:outline-none"
                    >
                      {availablePersonalities.map((entry) => (
                        <option key={entry.key} value={entry.key}>{entry.label}</option>
                      ))}
                    </select>
                  </div>

                  <button
                    type="button"
                    onClick={handleAddBots}
                    disabled={submitting || !selectedQuickPersonality || openSeats <= 0}
                    className="w-full rounded-2xl bg-cyan-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:bg-gray-800 disabled:text-gray-500"
                  >
                    {submitting ? 'Adding bots…' : 'Add Bots'}
                  </button>
                </div>

                <PersonalitySummary personality={selectedQuickPersonality} />
              </div>
            </div>

            <div className="rounded-3xl border border-gray-800 bg-gray-950/80 p-5 space-y-4">
              <div>
                <p className="text-sm font-semibold text-white">Advanced</p>
                <p className="mt-1 text-xs text-gray-400">Adjust difficulty and personality per bot without removing them from the lobby.</p>
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
                    const compatiblePersonalities = personalitiesByDifficulty[bot.bot_difficulty] || [];
                    const selectedBotPersonality = compatiblePersonalities.find((entry) => entry.key === bot.bot_persona)
                      || personalities.find((entry) => entry.key === bot.bot_persona)
                      || null;
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
                            Personality
                            <select
                              value={bot.bot_persona}
                              disabled={rowBusy}
                              onChange={(event) => updateBotPersona(bot, event.target.value)}
                              className="mt-2 w-full rounded-xl border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white focus:border-cyan-500 focus:outline-none"
                            >
                              {compatiblePersonalities.map((entry) => (
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
                              {selectedBotPersonality?.label || bot.bot_persona_label || bot.bot_persona}
                            </span>
                          </div>
                          <p className="text-sm text-gray-300">
                            {selectedBotPersonality?.short_description || bot.bot_persona_description}
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