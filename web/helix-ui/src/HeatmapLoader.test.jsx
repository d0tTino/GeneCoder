import { render, waitFor } from '@testing-library/react';
import { afterEach, beforeAll, expect, test, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import HeatmapLoader from './HeatmapLoader.jsx';

global.fetch = vi.fn((url) => {
  if (url.endsWith('gc-array')) {
    return Promise.resolve({ json: () => Promise.resolve({ gc_array: [0, 1] }) });
  }
  return Promise.resolve({ json: () => Promise.resolve({ hp_array: [1, 1] }) });
});

afterEach(() => {
  vi.restoreAllMocks();
});

beforeAll(() => {
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
    clearRect: vi.fn(),
    beginPath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    closePath: vi.fn(),
    fill: vi.fn(),
    fillRect: vi.fn(),
    fillText: vi.fn(),
  }));
});

test('fetches arrays and renders heatmaps', async () => {
  const { container } = render(<HeatmapLoader sequence="AC" />);
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  expect(container.querySelector('canvas')).toBeInTheDocument();
});
