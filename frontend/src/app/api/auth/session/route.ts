import { cookies } from "next/headers";

import { SESSION_COOKIE_NAME, verifySessionToken } from "@/lib/server-auth";


export async function GET(): Promise<Response> {
  const cookieStore = await cookies();
  const authenticated = verifySessionToken(cookieStore.get(SESSION_COOKIE_NAME)?.value);
  return Response.json(
    { authenticated },
    { headers: { "Cache-Control": "no-store" } },
  );
}
