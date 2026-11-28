// Init script for `100x shots --init-script`. It runs before the page loads, so the game boots into a late game save.
//   100x shots http://localhost:5173 --init-script .100x/must-not-break/seed-localstorage.js --label must-not-break --matrix all
// 1. Find the save key. Run the game once, then read Object.keys(localStorage) in the console.
// 2. Copy one real save, scale the numbers up, and keep its shape.
// 3. Check the screenshots for clipped or overlapping numbers, and read the console findings for NaN and exceptions.
(() => {
  const KEY = 'REPLACE_WITH_THE_REAL_SAVE_KEY';
  const hoursAway = 8;
  const save = {
    coins: 1.234e45, // late game magnitudes. Try 1e15, 1e60, 1e300 and 1e308 in turn. They break formatting and layout differently.
    gems: 123456789,
    owned: [999, 500, 250, 120, 60],
    prestige: 12,
    lastSeen: Date.now() - hoursAway * 3600 * 1000, // exercises offline progress on load
  };
  localStorage.setItem(KEY, JSON.stringify(save));
})();
