/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Discord-like color palette
        discord: {
          dark: '#2C2F33',
          darker: '#23272A',
          accent: '#5865F2',
          'accent-hover': '#4752C4',
          green: '#57F287',
          yellow: '#FEE75C',
          red: '#ED4245',
          gray: '#99AAB5',
          'light-gray': '#B9BBBE',
        },
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
      },
    },
  },
  plugins: [],
};
