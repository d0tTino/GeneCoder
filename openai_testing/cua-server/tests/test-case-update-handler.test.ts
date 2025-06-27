import { testCaseUpdateHandler } from '../src/handlers/test-case-update-handler';

describe('testCaseUpdateHandler', () => {
  it('updates status to fail', async () => {
    const emit = jest.fn();
    const socket: any = { emit, data: {} };
    await testCaseUpdateHandler(socket, 'fail');
    expect(socket.data.testCaseStatus).toBe('fail');
    expect(emit).toHaveBeenCalledWith('message', expect.any(String));
  });

  it('updates status to pass', async () => {
    const emit = jest.fn();
    const socket: any = { emit, data: {} };
    await testCaseUpdateHandler(socket, 'pass');
    expect(socket.data.testCaseStatus).toBe('pass');
    expect(emit).toHaveBeenCalledWith('message', expect.any(String));
  });
});
