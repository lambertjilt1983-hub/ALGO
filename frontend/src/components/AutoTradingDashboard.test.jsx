import { describe, it, expect } from 'vitest';
import React from 'react';

// Import the function to test
import { getEntryReadiness } from './aiGateLogic.js';

function makeSignal(overrides = {}) {
  return {
    quality: 90,
    confirmation_score: 90,
    ai_edge_score: 60,
    breakout_score: 80,
    momentum_score: 80,
    entry_price: 100,
    target: 110,
    stop_loss: 95,
    breakout_confirmed: true,
    momentum_confirmed: true,
    resistance: 120,
    support: 90,
    ...overrides,
  };
}

describe('getEntryReadiness AI gate resistance/support', () => {
  it('should pass when resistance and support are present and valid', () => {
    const signal = makeSignal();
    const result = getEntryReadiness(signal);
    expect(result.pass).toBe(true);
    expect(result.reasons.join(' ')).not.toMatch(/resistance|support/i);
  });

  it('should fail if resistance is missing', () => {
    const signal = makeSignal({ resistance: undefined });
    const result = getEntryReadiness(signal);
    expect(result.pass).toBe(false);
    expect(result.reasons.join(' ')).toMatch(/resistance/i);
  });

  it('should fail if support is missing', () => {
    const signal = makeSignal({ support: undefined });
    const result = getEntryReadiness(signal);
    expect(result.pass).toBe(false);
    expect(result.reasons.join(' ')).toMatch(/support/i);
  });

  it('should fail if resistance is zero or invalid', () => {
    const signal = makeSignal({ resistance: 0 });
    const result = getEntryReadiness(signal);
    expect(result.pass).toBe(false);
    expect(result.reasons.join(' ')).toMatch(/resistance/i);
  });

  it('should fail if support is zero or invalid', () => {
    const signal = makeSignal({ support: 0 });
    const result = getEntryReadiness(signal);
    expect(result.pass).toBe(false);
    expect(result.reasons.join(' ')).toMatch(/support/i);
  });
});
