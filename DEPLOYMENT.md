# SpendLens Railway Deployment

SpendLens supports two Railway layouts. In both layouts, the browser reaches only
the authenticated Next.js surface. FastAPI requires a bearer token, and PostgreSQL
must not receive a public domain.

## Free Plan Layout

Railway Free allows one project with three services. When another service already
uses one slot, deploy SpendLens with the root `Dockerfile` as two services:

- `spendlens`: public combined Next.js and FastAPI container.
- `Postgres`: private managed PostgreSQL service.

The combined service runs FastAPI on `127.0.0.1:8000` and Next.js on Railway's
public `PORT`. The root `railway.toml` health-checks `/api/auth/session`.

Set these variables on `spendlens`:

    PORT=3000
    API_BASE_URL=http://127.0.0.1:8000
    APP_ENVIRONMENT=production
    APP_TIMEZONE=Asia/Kolkata
    DATABASE_URL=${{Postgres.DATABASE_URL}}
    SPENDLENS_COOKIE_SECURE=true
    SPENDLENS_API_TOKEN=<generated secret>
    SPENDLENS_LOGIN_PASSWORD=<generated secret>
    SPENDLENS_SESSION_SECRET=<generated secret>

Deploy the repository root to `spendlens`. Generate a Railway domain only for
that service. For India, place both services in Southeast Asia.

## Standard Layout

On Hobby or above, use three services in a dedicated SpendLens project:

- `web`: public Next.js service with the login page and authenticated API proxy.
- `api`: private FastAPI service protected by a bearer token.
- `Postgres`: private managed PostgreSQL service.

| Service | Root directory | Config file |
| --- | --- | --- |
| api | /backend | /backend/railway.toml |
| web | /frontend | /frontend/railway.toml |

Set these variables on `api`:

    PORT=8000
    APP_ENVIRONMENT=production
    APP_TIMEZONE=Asia/Kolkata
    DATABASE_URL=${{Postgres.DATABASE_URL}}
    SPENDLENS_API_TOKEN=<generated secret>

Set these variables on `web`:

    PORT=3000
    API_BASE_URL=http://${{api.RAILWAY_PRIVATE_DOMAIN}}:${{api.PORT}}
    SPENDLENS_API_TOKEN=<same generated API secret>
    SPENDLENS_LOGIN_PASSWORD=<generated secret>
    SPENDLENS_SESSION_SECRET=<generated secret>

## Data Migration

A new Railway database starts empty. Before switching to the deployed app:

1. Create a PostgreSQL custom-format dump of only the local SpendLens database.
2. Confirm the Railway target database is empty.
3. Restore the dump with `--no-owner --no-privileges`.
4. Run `alembic upgrade head` against Railway PostgreSQL.
5. Compare table counts and dashboard summary values with local SpendLens.

## Security Checks

- Visiting the web domain without a session redirects to `/login`.
- Wrong passwords return `401`.
- Authenticated proxy requests return `200`.
- The session cookie is `HttpOnly`, `SameSite=Lax`, and `Secure` in production.
- Logout invalidates access to protected proxy routes.
- PostgreSQL has no public Railway domain.