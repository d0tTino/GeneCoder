import React, { useEffect, useState } from 'react';

export default function CatalogBrowser() {
  const [plugins, setPlugins] = useState(null);
  const [selectedRatings, setSelectedRatings] = useState({});
  const [ratings, setRatings] = useState({});

  useEffect(() => {
    fetch('/catalog/plugins')
      .then((r) => r.json())
      .then((data) => setPlugins(data.plugins || []));
  }, []);

  const rate = async (name) => {
    const rating = selectedRatings[name];
    if (!rating) return;
    const resp = await fetch('/catalog/plugins/rate', {
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
      <h1>Catalog Browser</h1>
      <ul>
        {plugins.map((p) => (
          <li key={`${p.name}-${p.version}`}>
            <strong>{p.name}</strong> v{p.version}{' '}
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
            {typeof p.stars === 'number' && (
              <span> ⭐{p.stars.toFixed(1)}</span>
            )}
            {ratings[p.name] && <span> ⭐{ratings[p.name].toFixed(1)}</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}
