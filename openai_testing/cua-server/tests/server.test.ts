import http from 'http';

const originalCreateServer = http.createServer;
let createdServer: http.Server;

beforeAll(() => {
  jest.spyOn(http, 'createServer').mockImplementation((listener) => {
    createdServer = originalCreateServer(listener);
    return createdServer;
  });
});

afterAll(async () => {
  await new Promise((resolve) => createdServer?.close(resolve));
});

describe('server startup', () => {
  it('responds on root', async () => {
    const port = 8130;
    process.env.SOCKET_PORT = String(port);
    process.env.OPENAI_API_KEY = 'test';
    const serverModule = await import('../src/index');
    await new Promise((resolve) => setTimeout(resolve, 1000));
    const data = await new Promise<string>((resolve, reject) => {
      http.get(`http://localhost:${port}`, (res) => {
        let text = '';
        res.on('data', (d) => (text += d));
        res.on('end', () => resolve(text));
      }).on('error', reject);
    });
    expect(data).toContain('Socket.IO server is running');
  });
});
