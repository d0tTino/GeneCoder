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
