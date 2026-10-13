# Контекст сборки — корень репозитория (npm workspaces).
FROM node:22-alpine AS deps
WORKDIR /repo
COPY package.json package-lock.json ./
COPY packages/blocks/package.json packages/blocks/
COPY frontend/package.json frontend/
COPY sites/package.json sites/
RUN npm ci --workspace @sk-events/sites --include-workspace-root=false --ignore-scripts

FROM deps AS dev
COPY packages/blocks packages/blocks
COPY sites sites
WORKDIR /repo/sites
CMD ["npx", "nuxt", "dev", "--host", "0.0.0.0"]

FROM deps AS build
COPY packages/blocks packages/blocks
COPY sites sites
RUN npm run build --workspace @sk-events/sites

FROM node:22-alpine AS prod
WORKDIR /app
ENV NODE_ENV=production PORT=3000
COPY --from=build /repo/sites/.output ./.output
USER node
EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]
