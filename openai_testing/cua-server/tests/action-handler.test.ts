import { handleModelAction } from '../src/handlers/action-handler';

describe('handleModelAction', () => {
  it('handles click action', async () => {
    const click = jest.fn();
    const page = { mouse: { click } } as any;
    await handleModelAction(page, { type: 'click', x: 10, y: 20 });
    expect(click).toHaveBeenCalledWith(10, 20, { button: 'left' });
  });
});
