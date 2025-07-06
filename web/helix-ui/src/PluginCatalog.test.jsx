import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import PluginCatalog from './PluginCatalog.jsx';

global.fetch = vi.fn(() =>
  Promise.resolve({ json: () => Promise.resolve({ plugins: { demo: { description: 'Demo' } } }) })
);

afterEach(() => {
  vi.restoreAllMocks();
});

test('renders plugins and installs', async () => {
  render(<PluginCatalog />);
  expect(await screen.findByText(/Demo/)).toBeInTheDocument();
  fetch.mockResolvedValueOnce({ json: () => Promise.resolve({}) });
  const btn = screen.getByRole('button', { name: /install/i });
  fireEvent.click(btn);
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
});
