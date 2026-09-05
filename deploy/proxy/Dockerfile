# Reverse-proxy: Caddy + модуль rate limiting.
#
# Почему Caddy, а не nginx+certbot: автоматический TLS без второго контейнера
# и cron-обвязки (docs/DECISIONS.md). Rate limiting в стоковом Caddy нет —
# собираем с mholt/caddy-ratelimit через xcaddy. У модуля нет релизов,
# поэтому пин по коммиту (2026-06-12), базовый образ — по минорной версии.
FROM caddy:2.11-builder AS builder
RUN xcaddy build \
    --with github.com/mholt/caddy-ratelimit@5625512f24f6f59d6f64fb3aafe5eecff0b286db

FROM caddy:2.11
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
COPY Caddyfile /etc/caddy/Caddyfile
