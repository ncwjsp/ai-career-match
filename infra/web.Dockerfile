# Next.js frontend. Owner: M3 (C-06).
#
# Build from the repository root:
#   docker build -f infra/web.Dockerfile -t career-match-web .
# BACKEND_URL is read at runtime by next.config.ts, which proxies /backend/* to
# the API. It is a server-side variable on purpose: no backend URL, session
# cookie or credential belongs in the browser bundle.
FROM node:24.19.0-bookworm-slim AS deps
WORKDIR /srv
RUN corepack enable && corepack prepare pnpm@11.19.0 --activate
COPY apps/web/package.json apps/web/pnpm-lock.yaml apps/web/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

FROM node:24.19.0-bookworm-slim AS build
WORKDIR /srv
RUN corepack enable && corepack prepare pnpm@11.19.0 --activate
COPY --from=deps /srv/node_modules ./node_modules
COPY apps/web/ ./
COPY contracts/ ../../contracts/
RUN pnpm build

FROM node:24.19.0-bookworm-slim AS runtime
WORKDIR /srv
ENV NODE_ENV=production
RUN corepack enable && corepack prepare pnpm@11.19.0 --activate
COPY --from=build /srv ./
USER node
EXPOSE 3000
CMD ["pnpm", "start", "--", "--port", "3000"]
