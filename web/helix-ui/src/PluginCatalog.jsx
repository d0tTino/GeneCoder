import React, { useEffect, useState } from 'react';

export default function PluginCatalog() {
  const [plugins, setPlugins] = useState(null);
  const [installing, setInstalling] = useState({});
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState('name');
  const [minStars, setMinStars] = useState('');
  const [form, setForm] = useState({
    name: '',
    version: '',
    checksum: '',
    signature: '',
    token: '',
  });

  const load = () => {
    const params = new URLSearchParams();
    if (search) params.append('q', search);
    if (minStars) params.append('min_stars', minStars);
    fetch(`/plugins/search?${params.toString()}`)
      .then((r) => r.json())
      .then((data) => setPlugins(data.plugins || []));
  };

  useEffect(() => {
    load();
  }, [search, minStars]);

  const install = async (name) => {
    setInstalling((s) => ({ ...s, [name]: true }));
    await fetch('/plugins/install', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    setInstalling((s) => ({ ...s, [name]: false }));
  };

  const submit = async () => {
    const { name, version, checksum, signature, token } = form;
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    await fetch('/catalog/plugins', {
      method: 'POST',
      headers,
      body: JSON.stringify({ name, version, checksum, signature }),
    });
    setForm((f) => ({ ...f, name: '', version: '', checksum: '', signature: '' }));
    load();
  };

  if (!plugins) {
    return <div>Loading...</div>;
  }

  const sorted = [...plugins].sort((a, b) => {
    if (sortBy === 'stars') {
      return (b.stars || 0) - (a.stars || 0);
    }
    return a.name.localeCompare(b.name);
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
          Stars:
          <select value={minStars} onChange={(e) => setMinStars(e.target.value)}>
            <option value="">Any</option>
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>
                {n}+
              </option>
            ))}
          </select>
        </label>
        <label style={{ marginLeft: 10 }}>
          Sort:
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
            <option value="name">Name</option>
            <option value="stars">Stars</option>
          </select>
        </label>
      </div>
      <ul>
        {sorted.map((p) => (
          <li key={p.name}>
            <strong>{p.name}</strong>
            {p.author ? ` by ${p.author}` : ''}
            {p.description ? ` - ${p.description}` : ''}
            {typeof p.stars === 'number' && <span> ⭐{p.stars.toFixed(1)}</span>}
            <button onClick={() => install(p.name)} disabled={installing[p.name]}>
              {installing[p.name] ? 'Installing...' : 'Install'}
            </button>
          </li>
        ))}
      </ul>
      <h2>Submit Plugin</h2>
      <div>
        <input
          aria-label="Name"
          placeholder="Name"
          value={form.name}
          onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
        />
        <input
          aria-label="Version"
          placeholder="Version"
          value={form.version}
          onChange={(e) => setForm((f) => ({ ...f, version: e.target.value }))}
        />
        <input
          aria-label="Checksum"
          placeholder="Checksum"
          value={form.checksum}
          onChange={(e) => setForm((f) => ({ ...f, checksum: e.target.value }))}
        />
        <input
          aria-label="Signature"
          placeholder="Signature"
          value={form.signature}
          onChange={(e) => setForm((f) => ({ ...f, signature: e.target.value }))}
        />
        <input
          aria-label="Token"
          placeholder="Token"
          value={form.token}
          onChange={(e) => setForm((f) => ({ ...f, token: e.target.value }))}
        />
        <button onClick={submit}>Submit</button>
      </div>
    </div>
  );
}
