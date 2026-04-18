/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Bootstrap-ish palette used across the app
        primary: { DEFAULT: '#007bff', hover: '#0069d9' },
        danger:  { DEFAULT: '#d9363e', hover: '#c12e35' },
        accent:  { DEFAULT: '#646cff' },
      },
      fontFamily: {
        sans: ['system-ui', 'Avenir', 'Helvetica', 'Arial', 'sans-serif'],
        mono: ['ui-monospace', 'SF Mono', 'Menlo', 'Consolas', 'monospace'],
      },
      keyframes: {
        'btn-spin': { to: { transform: 'rotate(360deg)' } },
        'slide-in': {
          from: { transform: 'translateX(100%)', opacity: '0' },
          to:   { transform: 'translateX(0)',    opacity: '1' },
        },
        'fade-in': {
          from: { opacity: '0', transform: 'translateY(-5px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        'highlight-pulse': {
          '0%':   { backgroundColor: '#28a745' },
          '50%':  { backgroundColor: '#d4edda' },
          '100%': { backgroundColor: '#d4edda' },
        },
      },
      animation: {
        'btn-spin': 'btn-spin 0.6s linear infinite',
        'slide-in': 'slide-in 0.2s ease-out',
        'fade-in':  'fade-in 0.3s ease-in',
        'highlight-pulse': 'highlight-pulse 1s ease-in-out',
      },
    },
  },
  plugins: [],
};
