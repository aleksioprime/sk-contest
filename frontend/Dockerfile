FROM node:20-alpine AS build
ARG LOGGER=false
ENV VITE_LOGGER=$LOGGER
WORKDIR /app
COPY app/package*.json ./
RUN npm ci
COPY app/ ./
RUN npm run build

FROM nginx:alpine
ARG API_URL=https://flow.skeducator.ru
ENV API_URL=$API_URL
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx/nginx.conf /etc/nginx/templates/default.conf.template
EXPOSE 80
