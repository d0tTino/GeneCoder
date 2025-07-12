import { render, screen, fireEvent, waitFor } from '@testing-library/react';
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

test('submits a new score', async () => {
  render(<Scoreboard />);
  await screen.findAllByRole('listitem');
  fetch.mockResolvedValueOnce({ json: () => Promise.resolve({}) });
  fireEvent.change(screen.getAllByPlaceholderText(/name/i)[0], {
    target: { value: 'Carl' },
  });
  fireEvent.change(screen.getAllByPlaceholderText(/points/i)[0], {
    target: { value: '3' },
  });
  fireEvent.change(screen.getAllByPlaceholderText(/token/i)[0], {
    target: { value: 'tok' },
  });
  fireEvent.click(screen.getAllByRole('button', { name: /submit/i })[0]);
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  const call = fetch.mock.calls[1];
  expect(call[0]).toBe('/catalog/challenge');
  expect(call[1].headers.Authorization).toBe('Bearer tok');
  expect(JSON.parse(call[1].body)).toEqual({ name: 'Carl', points: 3 });
});
