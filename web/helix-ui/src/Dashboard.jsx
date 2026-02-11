import React, { useState } from 'react';
import HeatmapLoader from './HeatmapLoader.jsx';
import { toLegacyMetrics, toRunSchema } from './runSchema.js';

export default function Dashboard() {
  const [sequence, setSequence] = useState('ACGT');
  const [data, setData] = useState(null);
  const [deepdna, setDeepdna] = useState(null);

  const loadFile = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    const txt = await f.text();
    setSequence(txt.trim());
  };

  const analyze = async () => {
    const resp = await fetch('/dashboard/metrics', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dna_sequence: sequence }),
    });
    const json = await resp.json();
    setData(toRunSchema(json));
  };

  const decodeDeepdna = async () => {
    const resp = await fetch('/dashboard/deepdna', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        encoded: btoa(sequence),
        info: { model_name: 'deepdna-small' },
      }),
    });
    const json = await resp.json();
    setDeepdna(json);
  };

  return (
    <div style={{ padding: 20 }}>
      <h1>GeneCoder Dashboard</h1>
      <textarea
        rows={4}
        style={{ width: '100%' }}
        value={sequence}
        onChange={(e) => setSequence(e.target.value)}
      />
      <div>
        <input type="file" onChange={loadFile} />
      </div>
      <button onClick={analyze}>Analyze</button>
      <button onClick={decodeDeepdna}>DeepDNA Decode</button>
      {data && (
        <div>
          {(() => { const metrics = toLegacyMetrics(data); return (<>
          <p>GC Mean: {typeof metrics.gc_content === 'number' ? (metrics.gc_content * 100).toFixed(2) : 'n/a'}%</p>
          <p>GC Variance: {typeof metrics.gc_variance === 'number' ? metrics.gc_variance.toFixed(4) : 'n/a'}</p>
          <p>Max Homopolymer: {metrics.max_homopolymer ?? 'n/a'}</p>
          <p>Error Rate: {typeof metrics.error_rate === 'number' ? (metrics.error_rate * 100).toFixed(2) : 'n/a'}%</p>
          {metrics.plot && <img src={`data:image/png;base64,${metrics.plot}`} style={{ maxWidth: '100%' }} />}
          {metrics.oligo_metrics && metrics.oligo_metrics.gc_percentages?.length > 0 && (
            <div>
              <h3>Per-oligo metrics</h3>
              <ul>
                {metrics.oligo_metrics.gc_percentages.map((gcVal, idx) => {
                  const hp = metrics.oligo_metrics.max_homopolymers?.[idx];
                  const drop = metrics.oligo_metrics.dropout_flags?.[idx];
                  const ecc = metrics.oligo_metrics.ecc_success || {};
                  const eccSummary = Object.entries(ecc)
                    .map(([name, values]) => {
                      const v = Array.isArray(values) ? values[idx] : undefined;
                      return `${name}: ${v !== undefined ? (v * 100).toFixed(1) + '% success' : 'n/a'}`;
                    })
                    .join(' | ');
                  const outOfBounds =
                    (typeof gcVal === 'number' && (gcVal < 0.4 || gcVal > 0.6)) ||
                    (typeof hp === 'number' && hp > 8) ||
                    Boolean(drop);
                  const tooltip = `HP=${hp ?? 'n/a'} | Dropout=${drop ? 'yes' : 'no'} | ${eccSummary}`;
                  return (
                    <li
                      key={idx}
                      title={tooltip}
                      style={{ color: outOfBounds ? '#d32f2f' : 'inherit', fontWeight: outOfBounds ? '600' : '400' }}
                    >
                      Oligo {idx + 1}: {(gcVal * 100).toFixed(2)}%
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
          </>); })()}
          <HeatmapLoader sequence={sequence} />
          {deepdna && (
            <div>
              <p>DeepDNA corrected: {deepdna.corrected}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
