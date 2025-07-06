import React, { useState } from 'react';

export default function Design() {
  const [sequence, setSequence] = useState('ACGT');
  const [result, setResult] = useState(null);

  const validate = async () => {
    const r = await fetch('/design/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sequence })
    });
    setResult(await r.json());
  };

  const fix = async () => {
    const r = await fetch('/design/fix', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sequence })
    });
    const data = await r.json();
    setSequence(data.sequence);
    setResult(data);
  };

  return (
    <div>
      <textarea value={sequence} onChange={e => setSequence(e.target.value)} />
      <div>
        <button onClick={validate}>Validate</button>
        <button onClick={fix}>Fix</button>
      </div>
      {result && <pre>{JSON.stringify(result, null, 2)}</pre>}
    </div>
  );
}
