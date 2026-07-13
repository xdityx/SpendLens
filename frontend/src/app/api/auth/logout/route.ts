import { cookies } from "next/headers";

import { SESSION_COOKIE_NAME } from "@/lib/server-auth";


export async function POST(): Promise<Response> {
  const cookieStore = await cookies();
  cookieStore.delete(SESSION_COOKIE_NAME);
  return Response.json(
    { authenticated: false },
    { headers: { "Cache-Control": "no-store" } },
  );
}
