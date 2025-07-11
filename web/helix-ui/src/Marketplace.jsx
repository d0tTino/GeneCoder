import React, { useEffect, useState } from 'react';

export default function Marketplace() {
  const [plugins, setPlugins] = useState(null);
  const [installing, setInstalling] = useState({});
  const [selectedRatings, setSelectedRatings] = useState({});
  const [ratings, setRatings] = useState({});

  useEffect(() => {
    fetch('/catalog/plugins')
      .then((r) => r.json())
      .then((data) => setPlugins(data.plugins || []));
  }, []);

  const install = async (name) => {
    setInstalling((s) => ({ ...s, [name]: true }));
    await fetch('/plugins/install', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    setInstalling((s) => ({ ...s, [name]: false }));
  };

  const rate = async (name) => {
    const rating = selectedRatings[name];
    if (!rating) return;
    const resp = await fetch('/plugins/rate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, rating: Number(rating) }),
    });
    const json = await resp.json();
    setRatings((r) => ({ ...r, [name]: json.average }));
  };

  if (!plugins) {
    return <div>Loading...</div>;
  }

  return (
    <div style={{ padding: 20 }}>
      <h1>Plugin Marketplace</h1>
      <ul>
        {plugins.map((p) => (
          <li key={`${p.name}-${p.version}`}>
            <strong>{p.name}</strong> v{p.version}{' '}
            <button onClick={() => install(p.name)} disabled={installing[p.name]}>
              {installing[p.name] ? 'Installing...' : 'Install'}
            </button>{' '}
            <select
              value={selectedRatings[p.name] || ''}
              onChange={(e) =>
                setSelectedRatings((s) => ({ ...s, [p.name]: e.target.value }))
              }
            >
              <option value="">Rate...</option>
              {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
            <button onClick={() => rate(p.name)}>Rate</button>
            {ratings[p.name] && <span> ⭐{ratings[p.name].toFixed(1)}</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}
