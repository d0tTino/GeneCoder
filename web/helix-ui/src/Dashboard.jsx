import React, { useEffect, useState } from 'react';
import HeatmapLoader from './HeatmapLoader.jsx';
import { presentationPayloadFromMetrics, toLegacyMetrics, toRunSchema } from './runSchema.js';

export default function Dashboard() {
  const [sequence, setSequence] = useState('ACGT');
  const [data, setData] = useState(null);
  const [deepdna, setDeepdna] = useState(null);
  const [capabilities, setCapabilities] = useState(null);

  useEffect(() => {
    let active = true;
    fetch('/capabilities')
      .then((resp) => resp.json())
      .then((json) => { if (active) setCapabilities(json); })
      .catch(() => { if (active) setCapabilities({ execution_mode: 'local-only', queue_backend: 'none', remote_worker: false, supports_async_jobs: false, local_only: true }); });
    return () => { active = false; };
  }, []);

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
      {capabilities && (
        <section aria-label="runtime-capabilities" style={{ margin: '12px 0', padding: 12, border: '1px solid #ddd', borderRadius: 6 }}>
          <strong>Execution mode:</strong> {capabilities.execution_mode}
          <div>Queue backend: {capabilities.queue_backend}</div>
          {capabilities.remote_worker ? <div>Remote worker execution enabled.</div> : null}
          {capabilities.supports_async_jobs ? <button type="button" style={{ marginTop: 8 }}>Submit async job</button> : null}
        </section>
      )}
      {data && (
        <div>
          {(() => { const metrics = toLegacyMetrics(data); return (<>
          <p>GC Mean: {typeof metrics.gc_content === 'number' ? (metrics.gc_content * 100).toFixed(2) : 'n/a'}%</p>
          <p>GC Variance: {typeof metrics.gc_variance === 'number' ? metrics.gc_variance.toFixed(4) : 'n/a'}</p>
          <p>Max Homopolymer: {metrics.max_homopolymer ?? 'n/a'}</p>
          <p>Error Rate: {typeof metrics.error_rate === 'number' ? (metrics.error_rate * 100).toFixed(2) : 'n/a'}%</p>
          {metrics.plot && <img src={`data:image/png;base64,${metrics.plot}`} style={{ maxWidth: '100%' }} />}
          {(() => {
            const payload = presentationPayloadFromMetrics(metrics);
            if (!payload.oligo_records.length) return null;
            return (
              <div>
                <h3>Per-oligo metrics</h3>
                <ul>
                  {payload.oligo_records.map((record) => {
                    const idx = record.Index - 1;
                    const gcVal = record['GC%'];
                    const hp = record['Max Homopolymer'];
                    const drop = record.Dropout;
                    const eccSummary = Object.entries(record)
                      .filter(([k]) => k.startsWith('ECC:'))
                      .map(([k, v]) => `${k.slice(4)}: ${typeof v === 'number' ? (v * 100).toFixed(1) + '% success' : 'n/a'}`)
                      .join(' | ');
                    const outOfBounds =
                      (typeof gcVal === 'number' && (gcVal < payload.constraint_limits.gc_min || gcVal > payload.constraint_limits.gc_max)) ||
                      (typeof hp === 'number' && hp > payload.constraint_limits.max_homopolymer) ||
                      Boolean(drop);
                    const tooltip = `HP=${hp ?? 'n/a'} | Dropout=${drop ? 'yes' : 'no'} | ${eccSummary}`;
                    return (
                      <li
                        key={idx}
                        title={tooltip}
                        style={{ color: outOfBounds ? '#d32f2f' : 'inherit', fontWeight: outOfBounds ? '600' : '400' }}
                      >
                        Oligo {idx + 1}: {typeof gcVal === 'number' ? (gcVal * 100).toFixed(2) : 'n/a'}%
                      </li>
                    );
                  })}
                </ul>
              </div>
            );
          })()}
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
