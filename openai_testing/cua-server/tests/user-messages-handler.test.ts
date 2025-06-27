import { handleSocketMessage } from '../src/handlers/user-messages-handler';

jest.mock('../src/services/openai-cua-client', () => ({
  sendInputToModel: jest.fn(async () => ({ output: [] })),
}));

jest.mock('../src/lib/computer-use-loop', () => ({
  computerUseLoop: jest.fn(async () => ({ output: [{ type: 'message', content: [{ type: 'output_text', text: 'hi' }] }] })),
}), { virtual: true });

const { sendInputToModel } = require('../src/services/openai-cua-client');
const { computerUseLoop } = require('../src/lib/computer-use-loop');

describe('handleSocketMessage', () => {
  it('emits message from response', async () => {
    const screenshot = jest.fn(async () => Buffer.from('')); 
    const socket: any = { data: { page: { screenshot }, previousResponseId: undefined, lastCallId: undefined, testCaseReviewAgent: undefined }, emit: jest.fn() };
    await handleSocketMessage(socket, 'hello');
    expect(sendInputToModel).toHaveBeenCalled();
    expect(computerUseLoop).toHaveBeenCalled();
    expect(socket.emit).toHaveBeenCalledWith('message', 'hi');
  });
});
