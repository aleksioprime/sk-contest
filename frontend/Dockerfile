FROM node:20-bullseye AS builder

WORKDIR /usr/src/app

ENV PATH /app/node_modules/.bin:$PATH
ENV NODE_OPTIONS=--trace-deprecation

ARG VITE_LOGGING
ARG VITE_API_URL

ENV VITE_LOGGING=$VITE_LOGGING
ENV VITE_API_URL=$VITE_API_URL

COPY app/package.json ./
RUN npm install

COPY app ./

FROM builder AS dev
CMD ["npm", "run", "dev", "--", "--host"]

FROM builder AS prod-builder
RUN npm run build

FROM nginx:alpine AS prod

COPY --from=prod-builder /usr/src/app/dist /usr/share/nginx/html
COPY nginx/nginx.conf /etc/nginx/conf.d/default.conf

CMD ["nginx", "-g", "daemon off;"]
