import React, { useEffect, useRef, useState } from 'react';
import { toRunSchema } from './runSchema.js';

export default function MetricsCharts() {
  const [data, setData] = useState(null);
  const canvasRef = useRef(null);

  useEffect(() => {
    fetch('/bundle-metrics')
      .then((r) => r.json())
      .then((json) => setData(toRunSchema(json, "bundle")));
  }, []);

  useEffect(() => {
    if (!data || !canvasRef.current) return;
    const ctx = canvasRef.current.getContext('2d');
    const width = 400;
    const height = 200;
    canvasRef.current.width = width;
    canvasRef.current.height = height;
    ctx.clearRect(0, 0, width, height);
    const metrics = data.outcome?.metrics || {};
    const vals = [
      metrics.total_original_size || 0,
      metrics.total_dna_length || 0,
      metrics.avg_reads_per_successful_decode || 0,
    ];
    const labels = ['Bytes', 'Bases', 'Reads/Decode'];
    const maxVal = Math.max(...vals, 1);
    const barWidth = width / vals.length;
    vals.forEach((v, i) => {
      const barHeight = (v / maxVal) * (height - 20);
      ctx.fillStyle = '#4e79a7';
      ctx.fillRect(i * barWidth + 10, height - barHeight - 20, barWidth - 20, barHeight);
      ctx.fillStyle = '#000';
      ctx.textAlign = 'center';
      ctx.fillText(labels[i], i * barWidth + barWidth / 2, height - 5);
    });
  }, [data]);

  if (!data) {
    return <div>Loading metrics...</div>;
  }

  return (
    <div style={{ padding: 20 }}>
      <h2>Bundle Metrics</h2>
      <canvas ref={canvasRef} />
      <p>Files: {data.outcome?.metrics?.files ?? 0}</p>
      <p>Avg bits/nt: {Number(data.outcome?.metrics?.avg_bits_per_nt ?? 0).toFixed(2)}</p>
      <p>Avg cost/recovered bit: ${Number(data.outcome?.metrics?.avg_cost_per_recovered_bit ?? 0).toFixed(6)}</p>
      <p>Avg redundancy cost ratio: {Number(data.outcome?.metrics?.avg_redundancy_cost_ratio ?? 0).toFixed(3)}</p>
    </div>
  );
}
