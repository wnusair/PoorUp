import { PLAYER_COLORS, needsDarkText } from '../../utils/constants';

export default function ColorPicker({ selectedColor, takenColors = [], onSelect, disabled = false }) {
  return (
    <div className="space-y-2">
      <p className="text-sm text-gray-400 font-medium">Choose Your Color</p>
      <div className="grid grid-cols-5 gap-2">
        {PLAYER_COLORS.map((color) => {
          const isTaken = takenColors.includes(color) && color !== selectedColor;
          const isSelected = color === selectedColor;

          return (
            <button
              key={color}
              onClick={() => !isTaken && !disabled && onSelect(color)}
              disabled={isTaken || disabled}
              title={isTaken ? 'Taken' : color}
              className={[
                'w-10 h-10 rounded-full border-2 transition-all flex items-center justify-center text-xs font-bold',
                isTaken
                  ? 'opacity-30 cursor-not-allowed border-gray-600'
                  : isSelected
                  ? 'border-white scale-110 shadow-lg'
                  : 'border-transparent hover:border-gray-300 hover:scale-105 cursor-pointer',
              ].join(' ')}
              style={{ backgroundColor: color }}
            >
              {isSelected && (
                <span
                  className="block h-2.5 w-2.5 rounded-full border"
                  style={{
                    backgroundColor: needsDarkText(color) ? '#111' : '#fff',
                    borderColor: needsDarkText(color) ? 'rgba(255,255,255,0.7)' : 'rgba(17,24,39,0.7)',
                  }}
                />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
