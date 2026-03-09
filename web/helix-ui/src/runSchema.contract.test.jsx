import { describe, expect, it } from 'vitest';
import { presentationPayloadFromMetrics } from './runSchema.js';

describe('presentationPayloadFromMetrics contract', () => {
  it('normalizes limits and oligo records for shared UI rendering', () => {
    const metrics = {
      constraint_violations: { limits: { gc_min: 0.45, gc_max: 0.55, max_homopolymer: 5 } },
      oligo_metrics: {
        gc_percentages: [0.4, 0.5],
        max_homopolymers: [4, 6],
        dropout_flags: [0, 1],
        ecc_success: { rs: [1.0, 0.5] },
      },
    };

    const payload = presentationPayloadFromMetrics(metrics);

    expect(payload.constraint_limits).toEqual({ gc_min: 0.45, gc_max: 0.55, max_homopolymer: 5 });
    expect(payload.oligo_records).toEqual([
      { Index: 1, 'GC%': 0.4, 'Max Homopolymer': 4, Dropout: false, 'ECC:rs': 1.0 },
      { Index: 2, 'GC%': 0.5, 'Max Homopolymer': 6, Dropout: true, 'ECC:rs': 0.5 },
    ]);
  });
});
