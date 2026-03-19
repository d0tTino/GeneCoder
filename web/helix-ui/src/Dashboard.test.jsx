import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import Dashboard from './Dashboard.jsx';

const originalFetch = global.fetch;

beforeEach(() => {
  global.fetch = vi.fn((url) => {
    if (url === '/capabilities') {
      return Promise.resolve({ json: () => Promise.resolve({ execution_mode: 'local-only', queue_backend: 'none', remote_worker: false, supports_async_jobs: false, local_only: true }) });
    }
    return Promise.resolve({ json: () => Promise.resolve({}) });
  });
});

afterEach(() => {
  global.fetch = originalFetch;
  vi.restoreAllMocks();
});

test('suppresses async and remote affordances in local-only mode', async () => {
  render(<Dashboard />);

  await waitFor(() => expect(screen.getByLabelText('runtime-capabilities')).toBeInTheDocument());
  expect(screen.getByText(/Execution mode:/)).toHaveTextContent('Execution mode: local-only');
  expect(screen.getByText(/Queue backend:/)).toHaveTextContent('Queue backend: none');
  expect(screen.queryByText(/Remote worker execution enabled/i)).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /submit async job/i })).not.toBeInTheDocument();
});
