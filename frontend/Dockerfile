# Frontend image (spec §26). Finalized Day 24. Two-stage: build with Node, serve the static
# production output — `vite preview` is a dev convenience, not meant for this, so the built
# `dist/` is served with a plain static-file server instead.
FROM node:20-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Vite inlines import.meta.env.* into the static bundle at BUILD time, not runtime — so the
# API base URL must arrive as a build arg here, not as a docker-compose `environment:` entry
# on the final image (that would have no effect on already-built static files).
ARG VITE_apiBaseUrl=http://localhost:8000
ENV VITE_apiBaseUrl=$VITE_apiBaseUrl
RUN npm run build

FROM node:20-slim
WORKDIR /app
COPY --from=build /app/dist ./dist
RUN npm install -g serve

EXPOSE 5173
CMD ["serve", "-s", "dist", "-l", "5173"]
