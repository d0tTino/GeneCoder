import React, { useEffect, useState } from 'react';

export default function Scoreboard() {
  const [entries, setEntries] = useState(null);

  useEffect(() => {
    fetch('/catalog/challenge')
      .then((r) => r.json())
      .then((data) => setEntries(data.entries || {}));
  }, []);

  if (!entries) {
    return <div>Loading...</div>;
  }

  const sorted = Object.entries(entries).sort((a, b) => b[1] - a[1]);

  return (
    <div style={{ padding: 20 }}>
      <h1>Challenge Rankings</h1>
      <ol>
        {sorted.map(([name, points]) => (
          <li key={name}>
            {name} - {points} pts
          </li>
        ))}
      </ol>
    </div>
  );
}
