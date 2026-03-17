const GLOBAL_KEY = '__algoConsoleDeduperState';
const ORIGINALS_KEY = '__algoConsoleOriginalWriters';
const INSTALLED_KEY = '__algoConsoleDeduperInstalled';

const getRoot = () => (typeof globalThis !== 'undefined' ? globalThis : window);

const getStore = () => {
  const root = getRoot();
  if (!root[GLOBAL_KEY]) {
    root[GLOBAL_KEY] = new Map();
  }
  return root[GLOBAL_KEY];
};

const getOriginalWriters = () => {
  const root = getRoot();
  if (!root[ORIGINALS_KEY]) {
    root[ORIGINALS_KEY] = {
      log: console.log.bind(console),
      warn: console.warn.bind(console),
      error: console.error.bind(console),
    };
  }
  return root[ORIGINALS_KEY];
};

const clearPendingTimer = (entry) => {
  if (entry?.timerId) {
    clearTimeout(entry.timerId);
    entry.timerId = null;
  }
};

const emit = (level, text, args) => {
  const originals = getOriginalWriters();
  const writer = originals[level] || originals.log;
  writer(text, ...args);
};

const toLogMessage = (value) => {
  if (typeof value === 'string') return value;
  if (value instanceof Error) return value.message || 'Error';
  try {
    const serialized = JSON.stringify(value);
    return serialized || String(value);
  } catch {
    return String(value);
  }
};

export const dedupedConsole = (
  level,
  key,
  message,
  options = {},
  ...args
) => {
  const {
    burstWindowMs = 30000,
    flushDelayMs = 1200,
    summaryFormatter,
    emitFirst = true,
  } = options;

  const now = Date.now();
  const store = getStore();
  const entry = store.get(key);

  if (!entry || (now - entry.firstAt) > burstWindowMs) {
    if (entry) {
      clearPendingTimer(entry);
    }
    const newEntry = {
      level,
      message,
      args,
      count: 1,
      firstAt: now,
      lastAt: now,
      timerId: null,
      summaryFormatter,
      emitFirst,
    };
    newEntry.timerId = setTimeout(() => {
      const latest = store.get(key);
      if (latest && latest.count <= 1) {
        store.delete(key);
      }
    }, burstWindowMs);
    store.set(key, newEntry);
    if (emitFirst) {
      emit(level, message, args);
    }
    return;
  }

  entry.count += 1;
  entry.lastAt = now;
  entry.level = level;
  entry.message = message;
  entry.args = args;
  entry.summaryFormatter = summaryFormatter;
  entry.emitFirst = emitFirst;
  clearPendingTimer(entry);
  entry.timerId = setTimeout(() => {
    const latest = store.get(key);
    if (!latest) return;
    if (latest.count <= 1) {
      store.delete(key);
      return;
    }
    const formatter = typeof latest.summaryFormatter === 'function'
      ? latest.summaryFormatter
      : (msg, count) => `${msg} [x${count}]`;
    emit(latest.level, formatter(latest.message, latest.count), latest.args);
    store.delete(key);
  }, flushDelayMs);
};

export const logDeduped = (key, message, options, ...args) => dedupedConsole('log', key, message, options, ...args);
export const warnDeduped = (key, message, options, ...args) => dedupedConsole('warn', key, message, options, ...args);
export const errorDeduped = (key, message, options, ...args) => dedupedConsole('error', key, message, options, ...args);

export const installConsoleDeduper = (options = {}) => {
  const root = getRoot();
  if (root[INSTALLED_KEY]) return;

  const originals = getOriginalWriters();
  const { burstWindowMs = 45000, flushDelayMs = 900 } = options;

  ['log', 'warn', 'error'].forEach((level) => {
    console[level] = (...rawArgs) => {
      if (!rawArgs || rawArgs.length === 0) {
        originals[level]();
        return;
      }
      const [first, ...rest] = rawArgs;
      const message = toLogMessage(first);
      const key = `global:${level}:${message}`;
      const passArgs = typeof first === 'string' ? rest : rawArgs;
      dedupedConsole(level, key, message, { burstWindowMs, flushDelayMs }, ...passArgs);
    };
  });

  root[INSTALLED_KEY] = true;
};