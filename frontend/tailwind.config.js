/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      animation: {
        'pulse-fast': 'pulse 0.5s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'flash': 'flash 0.5s ease-in-out 3',
        'slide-up': 'slideUp 0.3s ease-out',
        'card-flip': 'cardFlip 0.6s ease-in-out',
        'dice-roll': 'diceRoll 0.5s ease-out',
        'uprising': 'uprisingFlash 0.4s ease-in-out 6',
      },
      keyframes: {
        flash: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.3' },
        },
        slideUp: {
          '0%': { transform: 'translateY(20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        cardFlip: {
          '0%': { transform: 'rotateY(0deg)' },
          '50%': { transform: 'rotateY(90deg)' },
          '100%': { transform: 'rotateY(0deg)' },
        },
        diceRoll: {
          '0%': { transform: 'rotate(0deg) scale(1)' },
          '25%': { transform: 'rotate(90deg) scale(1.1)' },
          '50%': { transform: 'rotate(180deg) scale(0.9)' },
          '75%': { transform: 'rotate(270deg) scale(1.1)' },
          '100%': { transform: 'rotate(360deg) scale(1)' },
        },
        uprisingFlash: {
          '0%, 100%': { opacity: '1', backgroundColor: '#ef4444' },
          '50%': { opacity: '0.7', backgroundColor: '#7f1d1d' },
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
  ],
};
