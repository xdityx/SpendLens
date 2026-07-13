import { cookies } from "next/headers";

import {
  createSessionToken,
  hasProductionAuthConfiguration,
  SESSION_COOKIE_NAME,
  SESSION_MAX_AGE_SECONDS,
  verifyLoginPassword,
} from "@/lib/server-auth";


interface LoginBody {
  password?: unknown;
}


export async function POST(request: Request): Promise<Response> {
  if (!hasProductionAuthConfiguration()) {
    return Response.json({ detail: "Authentication is not configured" }, { status: 503 });
  }

  let body: LoginBody;
  try {
    body = (await request.json()) as LoginBody;
  } catch {
    return Response.json({ detail: "Invalid login request" }, { status: 400 });
  }

  const password = typeof body.password === "string" ? body.password : "";
  if (!password || password.length > 512 || !verifyLoginPassword(password)) {
    await new Promise((resolve) => setTimeout(resolve, 350));
    return Response.json({ detail: "Incorrect password" }, { status: 401 });
  }

  const cookieStore = await cookies();
  cookieStore.set(SESSION_COOKIE_NAME, createSessionToken(), {
    httpOnly: true,
    maxAge: SESSION_MAX_AGE_SECONDS,
    path: "/",
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production" && process.env.SPENDLENS_COOKIE_SECURE !== "false",
  });

  return Response.json(
    { authenticated: true },
    { headers: { "Cache-Control": "no-store" } },
  );
}
