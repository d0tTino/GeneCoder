import React, { useEffect, useState } from 'react';

export default function PluginCatalog() {
  const [plugins, setPlugins] = useState(null);
  const [installing, setInstalling] = useState({});

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

  return (
    <div style={{ padding: 20 }}>
      <h1>Plugin Catalog</h1>
      <ul>
        {Object.entries(plugins).map(([name, meta]) => (
          <li key={name}>
            <strong>{name}</strong>
            {meta.description ? ` - ${meta.description}` : ''}
            <button onClick={() => install(name)} disabled={installing[name]}>
              {installing[name] ? 'Installing...' : 'Install'}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
