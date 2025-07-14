import React, { useEffect, useRef, useState } from 'react';

export default function MetricsCharts() {
  const [data, setData] = useState(null);
  const canvasRef = useRef(null);

  useEffect(() => {
    fetch('/bundle-metrics')
      .then((r) => r.json())
      .then(setData);
  }, []);

  useEffect(() => {
    if (!data || !canvasRef.current) return;
    const ctx = canvasRef.current.getContext('2d');
    const width = 400;
    const height = 200;
    canvasRef.current.width = width;
    canvasRef.current.height = height;
    ctx.clearRect(0, 0, width, height);
    const vals = [data.total_original_size, data.total_dna_length];
    const labels = ['Bytes', 'Bases'];
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
      <p>Files: {data.files}</p>
      <p>Avg bits/nt: {data.avg_bits_per_nt.toFixed(2)}</p>
    </div>
  );
}
