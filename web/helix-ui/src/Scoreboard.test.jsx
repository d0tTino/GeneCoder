import { render, screen } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import Scoreboard from './Scoreboard.jsx';

// Mock the challenge fetch
global.fetch = vi.fn(() =>
  Promise.resolve({
    json: () =>
      Promise.resolve({
        entries: {
          Bob: 30,
          Alice: 40,
        },
      }),
  })
);

afterEach(() => {
  vi.restoreAllMocks();
});

test('renders entries sorted by score', async () => {
  render(<Scoreboard />);
  const items = await screen.findAllByRole('listitem');
  expect(items[0]).toHaveTextContent('Alice - 40 pts');
  expect(items[1]).toHaveTextContent('Bob - 30 pts');
});
