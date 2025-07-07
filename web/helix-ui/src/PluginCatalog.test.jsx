import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import PluginCatalog from './PluginCatalog.jsx';

global.fetch = vi.fn(() =>
  Promise.resolve({
    json: () =>
      Promise.resolve({
        plugins: {
          a: { description: 'A plugin', stars: 2 },
          b: { description: 'B plugin', stars: 5 },
        },
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
  fireEvent.change(searchBox, { target: { value: 'b' } });
  expect(screen.queryByText(/A plugin/)).not.toBeInTheDocument();

  const sortSelect = screen.getByLabelText(/sort/i);
  fireEvent.change(sortSelect, { target: { value: 'stars' } });
  const items = screen.getAllByRole('listitem');
  expect(items[0]).toHaveTextContent('b');

  fetch.mockResolvedValueOnce({ json: () => Promise.resolve({}) });
  const btn = screen.getAllByRole('button', { name: /install/i })[0];
  fireEvent.click(btn);
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
});
