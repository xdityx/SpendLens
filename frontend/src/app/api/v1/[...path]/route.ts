import { cookies } from "next/headers";
import type { NextRequest } from "next/server";

import { SESSION_COOKIE_NAME, verifySessionToken } from "@/lib/server-auth";


interface ProxyContext {
  params: Promise<{ path: string[] }>;
}


function backendConfiguration(): { baseUrl: string; token: string } | null {
  const configuredBaseUrl = process.env.API_BASE_URL?.trim();
  const configuredToken = process.env.SPENDLENS_API_TOKEN?.trim();
  const baseUrl = configuredBaseUrl || (process.env.NODE_ENV === "production" ? "" : "http://127.0.0.1:8000");
  const token =
    configuredToken || (process.env.NODE_ENV === "production" ? "" : "spendlens-local-development-api-token");

  return baseUrl && token ? { baseUrl: baseUrl.replace(/\/$/, ""), token } : null;
}


async function proxyRequest(request: NextRequest, context: ProxyContext): Promise<Response> {
  const cookieStore = await cookies();
  if (!verifySessionToken(cookieStore.get(SESSION_COOKIE_NAME)?.value)) {
    return Response.json({ detail: "Authentication required" }, { status: 401 });
  }

  const configuration = backendConfiguration();
  if (!configuration) {
    return Response.json({ detail: "Backend proxy is not configured" }, { status: 503 });
  }

  const { path } = await context.params;
  const upstreamUrl = new URL(
    `${configuration.baseUrl}/api/v1/${path.map(encodeURIComponent).join("/")}`,
  );
  request.nextUrl.searchParams.forEach((value, key) => upstreamUrl.searchParams.append(key, value));

  const headers = new Headers();
  headers.set("Accept", request.headers.get("Accept") || "application/json");
  headers.set("Authorization", `Bearer ${configuration.token}`);
  const contentType = request.headers.get("Content-Type");
  if (contentType) {
    headers.set("Content-Type", contentType);
  }

  try {
    const upstream = await fetch(upstreamUrl, {
      body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer(),
      cache: "no-store",
      headers,
      method: request.method,
      redirect: "manual",
    });

    const responseHeaders = new Headers({ "Cache-Control": "no-store" });
    const upstreamContentType = upstream.headers.get("Content-Type");
    if (upstreamContentType) {
      responseHeaders.set("Content-Type", upstreamContentType);
    }

    return new Response(upstream.body, {
      headers: responseHeaders,
      status: upstream.status,
      statusText: upstream.statusText,
    });
  } catch {
    return Response.json({ detail: "SpendLens API is unavailable" }, { status: 502 });
  }
}


export const GET = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const DELETE = proxyRequest;
