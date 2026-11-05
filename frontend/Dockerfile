# Контекст сборки — корень репозитория (npm workspaces).
FROM node:22-alpine AS deps
WORKDIR /repo
COPY package.json package-lock.json ./
COPY frontend/package.json frontend/
RUN npm ci --workspace @sk-contest/frontend --include-workspace-root=false --ignore-scripts

FROM deps AS dev
COPY frontend frontend
WORKDIR /repo/frontend
CMD ["npx", "vite", "--host", "0.0.0.0"]

FROM deps AS build
COPY frontend frontend
RUN npm run build --workspace @sk-contest/frontend

FROM nginx:1.27-alpine AS prod
COPY infra/nginx/frontend.conf /etc/nginx/conf.d/default.conf
COPY --from=build /repo/frontend/dist /usr/share/nginx/html
