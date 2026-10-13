# Контекст сборки — корень репозитория (npm workspaces).
FROM node:22-alpine AS deps
WORKDIR /repo
COPY package.json package-lock.json ./
COPY packages/blocks/package.json packages/blocks/
COPY frontend/package.json frontend/
COPY sites/package.json sites/
RUN npm ci --workspace @sk-events/frontend --include-workspace-root=false --ignore-scripts

FROM deps AS dev
COPY packages/blocks packages/blocks
COPY frontend frontend
WORKDIR /repo/frontend
CMD ["npx", "vite", "--host", "0.0.0.0"]

FROM deps AS build
COPY packages/blocks packages/blocks
COPY frontend frontend
RUN npm run build --workspace @sk-events/frontend

FROM nginx:1.27-alpine AS prod
COPY infra/nginx/frontend.conf /etc/nginx/conf.d/default.conf
COPY --from=build /repo/frontend/dist /usr/share/nginx/html
