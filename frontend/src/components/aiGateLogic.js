// Extracted AI gate logic for unit testing and reuse
// This file is pure logic, no React dependencies

// Thresholds and constants (copy from dashboard or parametrize as needed)
const DEFAULT_THRESHOLDS = {
  quality_min: 72,
  confidence_min: 76,
  ai_edge_min: 42,
  rr_min: 1.45,
  confirmation_score_floor: 62,
  weak_both_quality_override: 90,
  weak_both_confidence_override: 92,
  max_fake_move_risk: 14,
  max_news_risk: 16,
  max_liquidity_spike_risk: 14,
  max_premium_distortion_risk: 12,
};

function enrichSignalWithAiMetrics(signal) {
  if (!signal) return signal;
  const existingAiEdge = Number(signal.ai_edge_score);
  const existingMomentum = Number(signal.momentum_score);
  const existingBreakout = Number(signal.breakout_score);
  const existingFakeRisk = Number(signal.fake_move_risk);
  if (
    Number.isFinite(existingAiEdge)
    && Number.isFinite(existingMomentum)
    && Number.isFinite(existingBreakout)
    && Number.isFinite(existingFakeRisk)
  ) {
    return signal;
  }
  const confidence = Number(signal.confirmation_score ?? signal.confidence ?? 0);
  const quality = Number(signal.quality_score ?? signal.quality ?? 0);
  const entry = Number(signal.entry_price ?? 0);
  const target = Number(signal.target ?? 0);
  const stop = Number(signal.stop_loss ?? 0);
  const rr = Number(signal.rr ?? (entry > 0 ? (Math.abs(target - entry) / Math.max(0.0001, Math.abs(entry - stop))) : 0));
  const rrScore = Math.min(100, Math.max(0, (rr / 1.6) * 100));
  const momentumScore = Math.min(100, Math.max(0, confidence * 0.75 + quality * 0.15 + rrScore * 0.10));
  const breakoutScore = Math.min(100, Math.max(0, quality * 0.5 + rrScore * 0.35 + confidence * 0.15));
  const fakeMoveRisk = Math.min(95, Math.max(5, 100 - (momentumScore * 0.45 + breakoutScore * 0.35 + confidence * 0.20)));
  const suddenNewsRisk = Math.min(95, Math.max(5, fakeMoveRisk * 0.55 + (100 - confidence) * 0.25));
  const liquiditySpikeRisk = Math.min(95, Math.max(5, fakeMoveRisk * 0.45 + (100 - rrScore) * 0.20));
  const premiumDistortionRisk = Math.min(95, Math.max(5, fakeMoveRisk * 0.40 + (100 - breakoutScore) * 0.20));
  const aiEdgeScore = Math.min(100, Math.max(0, momentumScore * 0.35 + breakoutScore * 0.35 + quality * 0.20 + rrScore * 0.10 - fakeMoveRisk * 0.20));
  // Fallback for timing-risk metadata
  const now = new Date();
  const ist = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Kolkata' }));
  const mins = ist.getHours() * 60 + ist.getMinutes();
  let timingWindow = 'NORMAL';
  let qtyMultiplier = 1.0;
  if (mins >= (9 * 60 + 15) && mins <= (9 * 60 + 35)) {
    timingWindow = 'OPENING';
    qtyMultiplier = 0.7;
  } else if (mins >= (14 * 60 + 55) && mins <= (15 * 60 + 30)) {
    timingWindow = 'PRE_CLOSE';
    qtyMultiplier = 0.7;
  } else if (mins >= (12 * 60 + 25) && mins <= (12 * 60 + 35)) {
    timingWindow = 'EVENT_WINDOW';
    qtyMultiplier = 0.8;
  }
  const breakoutHoldFallback = breakoutScore >= 55 && fakeMoveRisk <= 45;
  return {
    ...signal,
    rr,
    ai_edge_score: Number.isFinite(existingAiEdge) ? existingAiEdge : Number(aiEdgeScore.toFixed(2)),
    momentum_score: Number.isFinite(existingMomentum) ? existingMomentum : Number(momentumScore.toFixed(2)),
    breakout_score: Number.isFinite(existingBreakout) ? existingBreakout : Number(breakoutScore.toFixed(2)),
    fake_move_risk: Number.isFinite(existingFakeRisk) ? existingFakeRisk : Number(fakeMoveRisk.toFixed(2)),
    sudden_news_risk: Number.isFinite(Number(signal.sudden_news_risk ?? signal.news_risk)) ? Number(signal.sudden_news_risk ?? signal.news_risk) : Number(suddenNewsRisk.toFixed(2)),
    liquidity_spike_risk: Number.isFinite(Number(signal.liquidity_spike_risk)) ? Number(signal.liquidity_spike_risk) : Number(liquiditySpikeRisk.toFixed(2)),
    premium_distortion_risk: Number.isFinite(Number(signal.premium_distortion_risk ?? signal.premium_distortion)) ? Number(signal.premium_distortion_risk ?? signal.premium_distortion) : Number(premiumDistortionRisk.toFixed(2)),
    timing_risk: signal.timing_risk || timingWindow,
    breakout_hold_confirmed:
      typeof signal.breakout_hold_confirmed === 'boolean'
        ? signal.breakout_hold_confirmed
        : breakoutHoldFallback,
    timing_risk_profile:
      signal.timing_risk_profile && typeof signal.timing_risk_profile === 'object'
        ? signal.timing_risk_profile
        : { volatile: timingWindow !== 'NORMAL', window: timingWindow, qty_multiplier: qtyMultiplier },
    qty_reduced_for_timing:
      typeof signal.qty_reduced_for_timing === 'boolean'
        ? signal.qty_reduced_for_timing
        : (qtyMultiplier < 0.999),
  };
}

function getEntryReadiness(signal, thresholds = DEFAULT_THRESHOLDS) {
  if (!signal) {
    return { status: 'WAIT', pass: false, reasons: ['No signal'], thresholds };
  }
  const normalizedSignal = enrichSignalWithAiMetrics(signal);
  // For unit test, use static thresholds and skip adaptive logic
  const aiEdge = Number(normalizedSignal.ai_edge_score ?? 0);
  const momentum = Number(normalizedSignal.momentum_score ?? 0);
  const breakout = Number(normalizedSignal.breakout_score ?? 0);
  const fakeRisk = Number(normalizedSignal.fake_move_risk ?? 100);
  const confidence = Number(normalizedSignal.confirmation_score ?? normalizedSignal.confidence ?? 0);
  const newsRisk = Number(normalizedSignal.sudden_news_risk ?? 100);
  const liquidityRisk = Number(normalizedSignal.liquidity_spike_risk ?? 100);
  const premiumRisk = Number(normalizedSignal.premium_distortion_risk ?? 100);
  const entry = Number(normalizedSignal.entry_price ?? 0);
  const target = Number(normalizedSignal.target ?? 0);
  const stop = Number(normalizedSignal.stop_loss ?? 0);
  const rr = Number(normalizedSignal.rr ?? (entry > 0 ? (Math.abs(target - entry) / Math.max(0.0001, Math.abs(entry - stop))) : 0));
  const qualityScore = Number(normalizedSignal.quality_score ?? normalizedSignal.quality ?? 0);
  const marketRegime = String(normalizedSignal.market_regime || '').toUpperCase();
  const marketBias = String(normalizedSignal.market_bias || '').toUpperCase();
  const timingRisk = String(normalizedSignal.timing_risk || normalizedSignal?.timing_risk_profile?.window || '').toUpperCase();
  const breakoutHold = normalizedSignal.breakout_hold_confirmed;
  const breakoutConfirmed = normalizedSignal.breakout_confirmed;
  const momentumConfirmed = normalizedSignal.momentum_confirmed;
  const breakoutOk = breakoutConfirmed === true || (breakoutConfirmed == null && breakout >= thresholds.confirmation_score_floor);
  const momentumOk = momentumConfirmed === true || (momentumConfirmed == null && momentum >= thresholds.confirmation_score_floor);
  const checks = [
    { ok: qualityScore >= thresholds.quality_min, fail: `Quality ${qualityScore.toFixed(1)} < ${thresholds.quality_min}` },
    { ok: confidence >= thresholds.confidence_min, fail: `Confidence ${confidence.toFixed(1)} < ${thresholds.confidence_min}` },
    { ok: aiEdge >= thresholds.ai_edge_min, fail: `AI edge ${aiEdge.toFixed(1)} < ${thresholds.ai_edge_min}` },
    { ok: rr >= thresholds.rr_min, fail: `RR ${rr.toFixed(2)} < ${thresholds.rr_min}` },
    { ok: breakoutOk && momentumOk, fail: `Need confirmations: breakout=${String(breakoutConfirmed)}/${breakout.toFixed(1)}, momentum=${String(momentumConfirmed)}/${momentum.toFixed(1)}` },
    { ok: breakoutHold !== false, fail: 'Breakout Hold NOT confirmed' },
    { ok: timingRisk !== 'HIGH', fail: 'Timing Risk HIGH — entry blocked' },
    {
      ok: marketBias !== 'WEAK_BOTH' || (qualityScore >= thresholds.weak_both_quality_override && confidence >= thresholds.weak_both_confidence_override),
      fail: `Market Bias WEAK_BOTH (needs quality>=${thresholds.weak_both_quality_override} and confidence>=${thresholds.weak_both_confidence_override})`
    },
    { ok: fakeRisk <= thresholds.max_fake_move_risk, fail: `Fake Move Risk ${fakeRisk.toFixed(1)}% > limit ${thresholds.max_fake_move_risk}%` },
    { ok: newsRisk <= thresholds.max_news_risk, fail: `News Risk ${newsRisk.toFixed(1)}% > limit ${thresholds.max_news_risk}%` },
    { ok: liquidityRisk <= thresholds.max_liquidity_spike_risk, fail: `Liquidity Risk ${liquidityRisk.toFixed(1)}% > limit ${thresholds.max_liquidity_spike_risk}%` },
    { ok: premiumRisk <= thresholds.max_premium_distortion_risk, fail: `Premium Distortion ${premiumRisk.toFixed(1)}% > limit ${thresholds.max_premium_distortion_risk}%` },
    { ok: marketRegime !== 'LOW_VOLATILITY' && marketRegime !== 'CHOPPY', fail: `Market regime ${marketRegime || 'UNKNOWN'}` },
    // AI GATE: Resistance/Support must be present and valid
    {
      ok: normalizedSignal.resistance !== undefined && normalizedSignal.resistance !== null,
      fail: 'Missing resistance level'
    },
    {
      ok: normalizedSignal.support !== undefined && normalizedSignal.support !== null,
      fail: 'Missing support level'
    },
    {
      ok: Number(normalizedSignal.resistance) > 0,
      fail: 'Invalid resistance value'
    },
    {
      ok: Number(normalizedSignal.support) > 0,
      fail: 'Invalid support value'
    },
  ];
  const reasons = checks.filter(c => !c.ok).map(c => c.fail);
  const pass = reasons.length === 0;
  return {
    status: pass ? 'GO' : 'WAIT',
    pass,
    reasons,
    thresholds,
    rr,
    aiEdge,
    momentum,
    breakout,
    fakeRisk,
    confidence,
    newsRisk,
    liquidityRisk,
    premiumRisk,
  };
}

export { getEntryReadiness, enrichSignalWithAiMetrics, DEFAULT_THRESHOLDS };
