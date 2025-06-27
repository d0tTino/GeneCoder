import { handleTestCaseInitiated } from '../src/handlers/test-case-initiation-handler';

jest.mock('../src/agents/test-case-agent', () => {
  return jest.fn().mockImplementation(() => ({ invokeResponseAPI: jest.fn(async () => ({ step: 'ok' })) }));
});

type CuaLoopArgs = Parameters<typeof import('../src/handlers/cua-loop-handler').cuaLoopHandler>;

jest.mock('../src/handlers/cua-loop-handler', () => ({
  cuaLoopHandler: jest.fn(async () => undefined),
}));

jest.mock('../src/utils/testCaseUtils', () => ({
  convertTestCaseToSteps: jest.fn(() => 'script'),
}));

jest.mock('../src/agents/test-script-review-agent', () => {
  return jest.fn().mockImplementation(() => ({
    instantiateAgent: jest.fn(async () => ({ })),
    checkTestScriptStatus: jest.fn(async () => ({ })),
  }));
});

const { cuaLoopHandler } = require('../src/handlers/cua-loop-handler');
const { convertTestCaseToSteps } = require('../src/utils/testCaseUtils');


describe('handleTestCaseInitiated', () => {
  it('calls cuaLoopHandler with converted script', async () => {
    const emit = jest.fn();
    const socket: any = { emit, data: {} };
    await handleTestCaseInitiated(socket, { testCase: 'tc', url: 'http://x', userName: 'u', password: 'p', userInfo: 'i', loginRequired: false });
    expect(convertTestCaseToSteps).toHaveBeenCalled();
    expect(cuaLoopHandler).toHaveBeenCalled();
  });
});
