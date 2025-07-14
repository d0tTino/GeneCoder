import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeAll, expect, test, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import MetricsCharts from './MetricsCharts.jsx';

global.fetch = vi.fn(() =>
  Promise.resolve({
    json: () =>
      Promise.resolve({
        files: 1,
        total_original_size: 100,
        total_dna_length: 200,
        avg_bits_per_nt: 1.5,
      }),
  })
);

afterEach(() => {
  vi.restoreAllMocks();
});

beforeAll(() => {
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
    clearRect: vi.fn(),
    fillRect: vi.fn(),
    fillText: vi.fn(),
  }));
});

test('renders bundle metrics', async () => {
  render(<MetricsCharts />);
  expect(await screen.findByText(/Files:/)).toBeInTheDocument();
  await waitFor(() => expect(fetch).toHaveBeenCalled());
});
