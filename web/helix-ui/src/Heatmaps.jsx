import React, { useEffect, useRef } from 'react';

export default function Heatmaps({ gcArray, hpArray }) {
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

    const drawRibbon = (values, yOffset, color) => {
      if (!values || values.length === 0) return;
      const barWidth = width / values.length;
      ctx.beginPath();
      ctx.moveTo(0, yOffset + rowHeight);
      for (let i = 0; i < values.length; i++) {
        const y = yOffset + rowHeight - values[i] * rowHeight;
        ctx.lineTo(i * barWidth, y);
      }
      ctx.lineTo(width, yOffset + rowHeight);
      ctx.closePath();
      ctx.fillStyle = color;
      ctx.fill();
    };

    if (gcArray && gcArray.length > 0) {
      drawRibbon(gcArray, 0, 'rgba(0,0,255,0.3)');
    }

    if (hpArray && hpArray.length > 0) {
      const maxHp = Math.max(...hpArray, 1);
      drawRibbon(
        hpArray.map((x) => x / maxHp),
        rowHeight + 4,
        'rgba(255,0,0,0.3)'
      );
    }
  }, [gcArray, hpArray]);

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
