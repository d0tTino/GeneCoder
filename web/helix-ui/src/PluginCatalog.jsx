import React, { useEffect, useState } from 'react';

export default function PluginCatalog() {
  const [plugins, setPlugins] = useState(null);
  const [installing, setInstalling] = useState({});
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState('name');

  useEffect(() => {
    fetch('/plugins')
      .then((r) => r.json())
      .then((data) => setPlugins(data.plugins || {}));
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

  if (!plugins) {
    return <div>Loading...</div>;
  }

  const filtered = Object.entries(plugins).filter(([name, meta]) =>
    name.toLowerCase().includes(search.toLowerCase()) ||
    (meta.description || '').toLowerCase().includes(search.toLowerCase()),
  );

  const sorted = [...filtered].sort((a, b) => {
    if (sortBy === 'stars') {
      return (b[1].stars || 0) - (a[1].stars || 0);
    }
    return a[0].localeCompare(b[0]);
  });

  return (
    <div style={{ padding: 20 }}>
      <h1>Plugin Catalog</h1>
      <div style={{ marginBottom: 10 }}>
        <input
          placeholder="Search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <label style={{ marginLeft: 10 }}>
          Sort:
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
            <option value="name">Name</option>
            <option value="stars">Stars</option>
          </select>
        </label>
      </div>
      <ul>
        {sorted.map(([name, meta]) => (
          <li key={name}>
            <strong>{name}</strong>
            {meta.author ? ` by ${meta.author}` : ''}
            {meta.description ? ` - ${meta.description}` : ''}
            {typeof meta.stars === 'number' && (
              <span> ⭐{meta.stars.toFixed(1)}</span>
            )}
            <button onClick={() => install(name)} disabled={installing[name]}>
              {installing[name] ? 'Installing...' : 'Install'}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
