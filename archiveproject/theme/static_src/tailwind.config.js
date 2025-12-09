module.exports = {
  theme: {
    extend: {
      screens: {
        'xs': '500px',   // custom breakpoint
      },
    },
  },
  content: [
    "../templates/**/*.html",
    "../../templates/**/*.html",
    "./src/**/*.css"
  ],
}
