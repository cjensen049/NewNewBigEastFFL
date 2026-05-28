/** @type {import('tailwindcss').Config} */
export default {
  // Tell Tailwind which files to scan for class names so it only includes used styles
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {},
  },
  plugins: [],
}
