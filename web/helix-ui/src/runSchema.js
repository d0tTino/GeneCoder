export const RUN_SCHEMA_VERSION = '1.0';

const toNumber = (value) => {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  return null;
};

const asBoolean = (value) => {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'number') return value > 0;
  return null;
};

const decodeSuccessRate = (metrics) => {
  if (toNumber(metrics.decode_success_rate) !== null) return toNumber(metrics.decode_success_rate);
  const ecc = metrics.ecc_success_rates;
  if (!ecc || typeof ecc !== 'object') return null;
  const vals = Object.values(ecc).map(toNumber).filter((v) => v !== null);
  if (!vals.length) return null;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
};

export function toRunSchema(input, runId = 'run') {
  if (input?.schema_version && input?.outcome) return input;

  if (input && typeof input === 'object' && input.files !== undefined && input.total_original_size !== undefined) {
    return {
      schema_version: RUN_SCHEMA_VERSION,
      run_id: runId,
      source_format: 'bundle_metrics',
      stages: {},
      profiles: {},
      seeds: {},
      runtime: {},
      outcome: {
        throughput: toNumber(input.throughput),
        ber: toNumber(input.ber),
        dropout_rate: toNumber(input.dropout_rate),
        gc_stress: toNumber(input.gc_stress),
        homopolymer_stress: toNumber(input.homopolymer_stress),
        decode_success: asBoolean(input.decode_success),
        decode_success_rate: toNumber(input.decode_success_rate),
        metrics: input,
      },
    };
  }

  const metrics = (input && input.metrics && typeof input.metrics === 'object') ? input.metrics : (input || {});
  const successRate = decodeSuccessRate(metrics);
  const decodeSuccess = asBoolean(metrics.decode_success) ?? (successRate !== null ? successRate >= 1 : null);

  return {
    schema_version: RUN_SCHEMA_VERSION,
    run_id: input?.file || runId,
    source_format: 'manifest',
    stages: {},
    profiles: {
      encoding: input?.encoding_parameters?.method || null,
      simulation: metrics?.channel?.name || null,
      decode: metrics?.decode_method || metrics?.decoder || null,
    },
    seeds: {},
    runtime: {},
    outcome: {
      ber: toNumber(metrics.ber),
      throughput: toNumber(metrics.throughput),
      dropout_rate: toNumber(metrics.dropout_fraction ?? metrics.dropout_rate),
      gc_stress: toNumber(metrics.gc_variance),
      homopolymer_stress: toNumber(metrics.max_homopolymer),
      decode_success: decodeSuccess,
      decode_success_rate: successRate,
      metrics,
    },
  };
}

export function toLegacyMetrics(input) {
  const run = toRunSchema(input);
  const metrics = { ...(run.outcome?.metrics || {}) };
  if (metrics.decode_success_rate === undefined) metrics.decode_success_rate = run.outcome?.decode_success_rate;
  if (metrics.decode_success === undefined) metrics.decode_success = run.outcome?.decode_success;
  if (metrics.ber === undefined) metrics.ber = run.outcome?.ber;
  if (metrics.throughput === undefined) metrics.throughput = run.outcome?.throughput;
  if (metrics.dropout_fraction === undefined) metrics.dropout_fraction = run.outcome?.dropout_rate;
  if (metrics.gc_variance === undefined) metrics.gc_variance = run.outcome?.gc_stress;
  if (metrics.max_homopolymer === undefined) metrics.max_homopolymer = run.outcome?.homopolymer_stress;
  return metrics;
}


const parseBool = (value) => {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'number') return Number(value) !== 0;
  if (typeof value === 'string') return ['1', 'true', 'yes', 'on'].includes(value.trim().toLowerCase());
  return false;
};

export function presentationPayloadFromMetrics(metrics = {}) {
  const violations = metrics?.constraint_violations;
  const limits = (violations && typeof violations === 'object' && violations.limits && typeof violations.limits === 'object')
    ? violations.limits
    : {};
  const constraint_limits = {
    gc_min: Number.isFinite(Number(limits.gc_min)) ? Number(limits.gc_min) : 0.4,
    gc_max: Number.isFinite(Number(limits.gc_max)) ? Number(limits.gc_max) : 0.6,
    max_homopolymer: Number.isFinite(Number(limits.max_homopolymer)) ? Number(limits.max_homopolymer) : 8,
  };

  const oligo = metrics?.oligo_metrics && typeof metrics.oligo_metrics === 'object' ? metrics.oligo_metrics : {};
  const gc = Array.isArray(oligo.gc_percentages) ? oligo.gc_percentages.filter((v) => typeof v === 'number').map(Number) : [];
  const hp = Array.isArray(oligo.max_homopolymers) ? oligo.max_homopolymers.filter((v) => typeof v === 'number').map(Number) : [];
  const dropout = Array.isArray(oligo.dropout_flags) ? oligo.dropout_flags.map(parseBool) : [];

  const ecc = {};
  if (oligo.ecc_success && typeof oligo.ecc_success === 'object') {
    Object.entries(oligo.ecc_success).forEach(([name, values]) => {
      if (Array.isArray(values)) {
        const filtered = values.filter((v) => typeof v === 'number' || typeof v === 'boolean').map((v) => (typeof v === 'boolean' ? (v ? 1 : 0) : Number(v)));
        if (filtered.length) ecc[name] = filtered;
      }
    });
  }

  const maxLen = Math.max(gc.length, hp.length, dropout.length, ...Object.values(ecc).map((vals) => vals.length), 0);
  const oligo_records = Array.from({ length: maxLen }, (_, idx) => {
    const row = { Index: idx + 1 };
    if (idx < gc.length) row['GC%'] = gc[idx];
    if (idx < hp.length) row['Max Homopolymer'] = hp[idx];
    if (idx < dropout.length) row.Dropout = dropout[idx];
    Object.entries(ecc).forEach(([name, vals]) => {
      if (idx < vals.length) row[`ECC:${name}`] = vals[idx];
    });
    return row;
  });

  return { metrics, constraint_limits, oligo_records };
}
