import React, { useState } from 'react';
import HeatmapLoader from './HeatmapLoader.jsx';

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
    setData(json);
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
          <p>GC Content: {(data.gc_content * 100).toFixed(2)}%</p>
          <p>Max Homopolymer: {data.max_homopolymer}</p>
          <p>Error Rate: {(data.error_rate * 100).toFixed(2)}%</p>
          <img src={`data:image/png;base64,${data.plot}`} style={{ maxWidth: '100%' }} />
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
