export async function POST(request: Request) {
  const { username, password } = (await request.json()) as {
    username?: string;
    password?: string;
  };

  const expectedUser = process.env.ADMIN_USERNAME ?? "";
  const expectedPass = process.env.ADMIN_PASSWORD ?? "";

  if (username === expectedUser && password === expectedPass) {
    // TODO: replace with a proper JWT from your real auth provider
    return Response.json({ token: "dummy-jwt-token" });
  }

  return Response.json({ error: "Invalid credentials" }, { status: 401 });
}
