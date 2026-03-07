export const extractLiveBalance = (payload) => {
  if (!payload || typeof payload !== 'object') return null;

  const preferredKeys = [
    'available_balance',
    'available_cash',
    'live_balance',
    'balance',
    'net',
    'cash',
    'available',
    'total_balance',
  ];

  const seen = new Set();
  const stack = [payload];
  const candidates = [];

  while (stack.length) {
    const node = stack.pop();
    if (!node || typeof node !== 'object' || seen.has(node)) continue;
    seen.add(node);

    for (const [k, v] of Object.entries(node)) {
      if (v && typeof v === 'object') {
        stack.push(v);
        continue;
      }

      const num = Number(v);
      if (!Number.isFinite(num) || num < 0) continue;

      const key = String(k || '').toLowerCase();
      const rank = preferredKeys.indexOf(key);
      if (rank >= 0) {
        candidates.push({ num, rank });
      }
    }
  }

  if (!candidates.length) return null;
  candidates.sort((a, b) => a.rank - b.rank);
  return candidates[0].num;
};
