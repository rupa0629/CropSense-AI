# syntax=docker/dockerfile:1
FROM node:20-alpine AS builder
WORKDIR /app
ENV NODE_ENV=development
ARG VITE_API_BASE=/api
ENV VITE_API_BASE=${VITE_API_BASE}

COPY package.json package-lock.json ./
COPY vite.config.js ./
COPY index.html ./
COPY public ./public
COPY src ./src

RUN npm ci --legacy-peer-deps --silent
RUN npm run build

FROM nginx:stable-alpine AS runtime
RUN apk add --no-cache wget
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget --quiet --spider http://127.0.0.1:80 || exit 1
CMD ["nginx", "-g", "daemon off;"]
