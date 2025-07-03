import React, { useEffect, useRef } from 'react';

export default function Heatmaps({ gcPositions, gcValues, hpLengths }) {
  const canvasRef = useRef(null);
  const width = 600;
  const rowHeight = 40;

  useEffect(() => {
    const canvas = canvasRef.current;
    const totalHeight = rowHeight * 2 + 4;
    canvas.width = width;
    canvas.height = totalHeight;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, width, totalHeight);

    // GC content heatmap
    if (gcPositions && gcValues && gcValues.length > 0) {
      const barWidth = width / gcValues.length;
      for (let i = 0; i < gcValues.length; i++) {
        const intensity = gcValues[i];
        ctx.fillStyle = `rgba(0,0,255,${intensity})`;
        ctx.fillRect(i * barWidth, 0, barWidth, rowHeight);
      }
    }

    // Homopolymer length heatmap
    if (hpLengths && hpLengths.length > 0) {
      const maxHp = Math.max(...hpLengths, 1);
      const barWidth = width / hpLengths.length;
      for (let i = 0; i < hpLengths.length; i++) {
        const intensity = hpLengths[i] / maxHp;
        ctx.fillStyle = `rgba(255,0,0,${intensity})`;
        ctx.fillRect(i * barWidth, rowHeight + 4, barWidth, rowHeight);
      }
    }
  }, [gcPositions, gcValues, hpLengths]);

  return (
    <div style={{ width }}>
      <canvas ref={canvasRef} style={{ width: '100%', border: '1px solid #ccc' }} />
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
        <span>GC Content</span>
        <span>Homopolymer Length</span>
      </div>
    </div>
  );
}
