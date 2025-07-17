import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import CatalogBrowser from './CatalogBrowser.jsx';

global.fetch = vi.fn(() =>
  Promise.resolve({
    json: () =>
      Promise.resolve({
        plugins: [
          { name: 'a', version: '1.0', stars: 3 },
          { name: 'b', version: '1.1', stars: 2 },
        ],
      }),
  })
);

afterEach(() => {
  vi.restoreAllMocks();
});

test('renders and rates plugins', async () => {
  render(<CatalogBrowser />);
  expect(await screen.findByText(/a/)).toBeInTheDocument();
  fetch.mockResolvedValueOnce({ json: () => Promise.resolve({ average: 4 }) });
  fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: '4' } });
  fireEvent.click(screen.getAllByRole('button', { name: /rate/i })[0]);
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
});
