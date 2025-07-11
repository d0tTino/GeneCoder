import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import Marketplace from './Marketplace.jsx';

// Mock fetch for plugin list
global.fetch = vi.fn(() =>
  Promise.resolve({
    json: () =>
      Promise.resolve({
        plugins: [
          { name: 'a', version: '1.0' },
          { name: 'b', version: '1.1' },
        ],
      }),
  })
);

afterEach(() => {
  vi.restoreAllMocks();
});

test('renders plugins and handles actions', async () => {
  render(<Marketplace />);
  expect(await screen.findByText(/a/)).toBeInTheDocument();
  // Install first plugin
  fetch.mockResolvedValueOnce({ json: () => Promise.resolve({}) });
  const installBtn = screen.getAllByRole('button', { name: /install/i })[0];
  fireEvent.click(installBtn);
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  // Rate first plugin
  fetch.mockResolvedValueOnce({ json: () => Promise.resolve({ average: 5 }) });
  fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: '5' } });
  const rateBtn = screen.getAllByRole('button', { name: /rate/i })[0];
  fireEvent.click(rateBtn);
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(3));
});
