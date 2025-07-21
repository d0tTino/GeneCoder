import React, { useEffect, useState } from 'react';
import Heatmaps from './Heatmaps.jsx';

export default function HeatmapLoader({ sequence }) {
  const [gcArray, setGcArray] = useState(null);
  const [hpArray, setHpArray] = useState(null);

  useEffect(() => {
    if (!sequence) return;
    const load = async () => {
      const gcResp = await fetch('/gc-array', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dna_sequence: sequence })
      });
      const gcJson = await gcResp.json();
      setGcArray(gcJson.gc_array);

      const hpResp = await fetch('/homopolymer-array', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dna_sequence: sequence })
      });
      const hpJson = await hpResp.json();
      setHpArray(hpJson.hp_array);
    };
    load();
  }, [sequence]);

  if (!gcArray || !hpArray) return null;
  return <Heatmaps gcArray={gcArray} hpArray={hpArray} />;
}
