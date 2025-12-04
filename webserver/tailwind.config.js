/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/**/*.html", "./static/**/*.js"],
  darkMode: 'class',
  safelist: [
    // Badge background colors (light and dark)
    'bg-yellow-50', 'bg-yellow-950', 'bg-red-50', 'bg-red-950', 'bg-green-50', 'bg-green-950',
    'bg-purple-50', 'bg-purple-950', 'bg-blue-50', 'bg-blue-950', 'bg-indigo-50', 'bg-indigo-950',
    'bg-pink-50', 'bg-pink-950', 'bg-teal-50', 'bg-teal-950', 'bg-gray-50', 'bg-gray-950',
    'bg-amber-50', 'bg-amber-950', 'bg-lime-50', 'bg-lime-950', 'bg-cyan-50', 'bg-cyan-950',
    'bg-fuchsia-50', 'bg-fuchsia-950', 'bg-rose-50', 'bg-rose-950', 'bg-violet-50', 'bg-violet-950',
    'bg-sky-50', 'bg-sky-950', 'bg-emerald-50', 'bg-emerald-950',
    
    // Badge text colors (light and dark)
    'text-yellow-700', 'text-yellow-300', 'text-red-700', 'text-red-300', 'text-green-700', 'text-green-300',
    'text-purple-700', 'text-purple-300', 'text-blue-700', 'text-blue-300', 'text-indigo-700', 'text-indigo-300',
    'text-pink-700', 'text-pink-300', 'text-teal-700', 'text-teal-300', 'text-gray-700', 'text-gray-300',
    'text-amber-700', 'text-amber-300', 'text-lime-700', 'text-lime-300', 'text-cyan-700', 'text-cyan-300',
    'text-fuchsia-700', 'text-fuchsia-300', 'text-rose-700', 'text-rose-300', 'text-violet-700', 'text-violet-300',
    'text-sky-700', 'text-sky-300', 'text-emerald-700', 'text-emerald-300',
    
    // Badge border colors with opacity (must be explicit for JIT)
    'border-yellow-600/10', 'border-yellow-400/20', 'border-red-600/10', 'border-red-400/20',
    'border-green-600/10', 'border-green-400/20', 'border-purple-600/10', 'border-purple-400/20',
    'border-blue-600/10', 'border-blue-400/20', 'border-indigo-600/10', 'border-indigo-400/20',
    'border-pink-600/10', 'border-pink-400/20', 'border-teal-600/10', 'border-teal-400/20',
    'border-gray-600/10', 'border-gray-400/20', 'border-amber-600/10', 'border-amber-400/20',
    'border-lime-600/10', 'border-lime-400/20', 'border-cyan-600/10', 'border-cyan-400/20',
    'border-fuchsia-600/10', 'border-fuchsia-400/20', 'border-rose-600/10', 'border-rose-400/20',
    'border-violet-600/10', 'border-violet-400/20', 'border-sky-600/10', 'border-sky-400/20',
    'border-emerald-600/10', 'border-emerald-400/20',
    
    // SVG fill colors for dots (light and dark)
    'fill-yellow-500', 'fill-yellow-400', 'fill-red-500', 'fill-red-400', 'fill-green-500', 'fill-green-400',
    'fill-purple-500', 'fill-purple-400', 'fill-blue-500', 'fill-blue-400', 'fill-indigo-500', 'fill-indigo-400',
    'fill-pink-500', 'fill-pink-400', 'fill-teal-500', 'fill-teal-400', 'fill-gray-500', 'fill-gray-400',
    'fill-amber-500', 'fill-amber-400', 'fill-lime-500', 'fill-lime-400', 'fill-cyan-500', 'fill-cyan-400',
    'fill-fuchsia-500', 'fill-fuchsia-400', 'fill-rose-500', 'fill-rose-400', 'fill-violet-500', 'fill-violet-400',
    'fill-sky-500', 'fill-sky-400', 'fill-emerald-500', 'fill-emerald-400',
  ],
  theme: {
    extend: {
      fontFamily: {
        'sans': ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'Liberation Mono', 'Courier New', 'monospace'],
        'mono': ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'Liberation Mono', 'Courier New', 'monospace'],
      },
      colors: {
        // Label Maker Light Mode (white background, black text, yellow accents)
        primary: '#FCD34D',      // Bright yellow
        secondary: '#FEFCE8',    // Very light yellow
        accent: '#EAB308',       // Golden yellow
        highlight: '#FDE047',    // Light yellow
        background: '#FFFFFF',   // Pure white
        surface: '#FAFAF9',      // Off-white
        text: '#1C1917',         // Almost black
        'text-primary': '#1C1917',

        // Label Maker Dark Mode (black background, white text, yellow accents)
        'dark-primary': '#1C1917',    // Almost black
        'dark-secondary': '#292524',  // Dark gray
        'dark-accent': '#FCD34D',     // Bright yellow
        'dark-highlight': '#FDE047',  // Light yellow
        'dark-background': '#0C0A09', // Pure black
        'dark-surface': '#1C1917',    // Almost black
        'dark-text': '#FAFAF9',       // Off-white
        'dark-input-background': '#292524',
        'dark-input-text': '#FAFAF9',
      },
    },
  },
  plugins: [],
}