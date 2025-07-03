import React, { useState } from 'react';
import Heatmaps from './Heatmaps.jsx';

export default function Dashboard() {
  const [sequence, setSequence] = useState('ACGT');
  const [data, setData] = useState(null);
  const [plotData, setPlotData] = useState(null);

  const analyze = async () => {
    const resp = await fetch('/dashboard/metrics', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dna_sequence: sequence }),
    });
    const json = await resp.json();
    setData(json);

    const respPlot = await fetch('/dashboard/plot-data', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dna_sequence: sequence }),
    });
    const plotJson = await respPlot.json();
    setPlotData(plotJson);
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
      <button onClick={analyze}>Analyze</button>
      {data && (
        <div>
          <p>GC Content: {(data.gc_content * 100).toFixed(2)}%</p>
          <p>Max Homopolymer: {data.max_homopolymer}</p>
          <p>Error Rate: {(data.error_rate * 100).toFixed(2)}%</p>
          <img src={`data:image/png;base64,${data.plot}`} style={{ maxWidth: '100%' }} />
          {plotData && (
            <Heatmaps
              gcPositions={plotData.gc_positions}
              gcValues={plotData.gc_values}
              hpLengths={plotData.hp_lengths}
            />
          )}
        </div>
      )}
    </div>
  );
}
