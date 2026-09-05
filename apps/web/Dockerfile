# Search For Research — фронт (SFR-4). Multi-stage: standalone-сборка Next
# без node_modules в рантайме (~200 МБ вместо гигабайта).
#
# NEXT_PUBLIC_* инлайнятся в бандл на сборке — передаются build-аргами, не
# рантайм-окружением. next.config сам упадёт, если NEXT_PUBLIC_SITE_URL пуст.
FROM node:24-slim AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG NEXT_PUBLIC_SITE_URL
ARG NEXT_PUBLIC_CLAIM_EMAIL=""
ENV NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL \
    NEXT_PUBLIC_CLAIM_EMAIL=$NEXT_PUBLIC_CLAIM_EMAIL \
    NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:24-slim

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000

WORKDIR /app

# Не root: пользователь node есть в базовом образе (REVIEW_SFR3 Medium).
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
USER node

EXPOSE 3000
# В slim-образе нет curl/wget — проверяем родным fetch. Лендинг рендерится
# и с упавшим API (деградация), так что это чек самого Next, не бэкенда.
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=5 \
    CMD ["node", "-e", "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"]

CMD ["node", "server.js"]
