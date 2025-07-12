import React, { useEffect, useState } from 'react';

export default function Scoreboard() {
  const [entries, setEntries] = useState(null);
  const [name, setName] = useState('');
  const [points, setPoints] = useState('');
  const [token, setToken] = useState('');

  const load = () => {
    fetch('/catalog/challenge')
      .then((r) => r.json())
      .then((data) => setEntries(data.entries || {}));
  };

  useEffect(() => {
    load();
  }, []);

  if (!entries) {
    return <div>Loading...</div>;
  }

  const submit = async (e) => {
    e.preventDefault();
    await fetch('/catalog/challenge', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ name, points: parseInt(points, 10) }),
    });
    setName('');
    setPoints('');
    load();
  };

  const sorted = Object.entries(entries).sort((a, b) => b[1] - a[1]);

  return (
    <div style={{ padding: 20 }}>
      <h1>Challenge Rankings</h1>
      <ol>
        {sorted.map(([n, p]) => (
          <li key={n}>
            {n} - {p} pts
          </li>
        ))}
      </ol>
      <form onSubmit={submit} style={{ marginTop: 20 }}>
        <input
          placeholder="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          placeholder="Points"
          type="number"
          value={points}
          onChange={(e) => setPoints(e.target.value)}
        />
        <input
          placeholder="Token"
          value={token}
          onChange={(e) => setToken(e.target.value)}
        />
        <button type="submit">Submit</button>
      </form>
    </div>
  );
}
