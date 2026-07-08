# ---- build stage ----
FROM node:22-slim AS builder
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml* .npmrc* ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

# ---- runtime stage ----
FROM node:22-slim
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.output ./.output
USER node
EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]