import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import PluginCatalog from './PluginCatalog.jsx';

global.fetch = vi.fn(() =>
  Promise.resolve({
    json: () =>
      Promise.resolve({
        plugins: [
          { name: 'a', description: 'A plugin', stars: 2 },
          { name: 'b', description: 'B plugin', stars: 5 },
        ],
      }),
  })
);

afterEach(() => {
  vi.restoreAllMocks();
});

test('renders plugins and installs', async () => {
  render(<PluginCatalog />);
  expect(await screen.findByText(/A plugin/)).toBeInTheDocument();

  const searchBox = screen.getByPlaceholderText(/search/i);
  fetch.mockResolvedValueOnce({
    json: () => Promise.resolve({ plugins: [{ name: 'b' }] }),
  });
  fireEvent.change(searchBox, { target: { value: 'b' } });
  await screen.findByText('b');

  const sortSelect = screen.getByLabelText(/sort/i);
  fireEvent.change(sortSelect, { target: { value: 'stars' } });
  const items = screen.getAllByRole('listitem');
  expect(items[0]).toHaveTextContent('b');

  fetch.mockResolvedValueOnce({ json: () => Promise.resolve({}) });
  const btn = screen.getAllByRole('button', { name: /install/i })[0];
  fireEvent.click(btn);
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(3));

  fetch.mockResolvedValueOnce({ json: () => Promise.resolve({ status: 'ok' }) });
  fireEvent.change(screen.getByLabelText(/name/i), { target: { value: 'x' } });
  fireEvent.change(screen.getByLabelText(/version/i), { target: { value: '1' } });
  fireEvent.change(screen.getByLabelText(/checksum/i), { target: { value: 'c' } });
  fireEvent.change(screen.getByLabelText(/token/i), { target: { value: 't' } });
  fireEvent.click(screen.getByRole('button', { name: /submit/i }));
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(4));
});
