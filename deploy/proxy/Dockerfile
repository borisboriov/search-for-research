# Reverse-proxy: Caddy + модуль rate limiting.
#
# Почему Caddy, а не nginx+certbot: автоматический TLS без второго контейнера
# и cron-обвязки (docs/DECISIONS.md). Rate limiting в стоковом Caddy нет —
# собираем с mholt/caddy-ratelimit через xcaddy. У модуля нет релизов,
# поэтому пин по коммиту (2026-06-12), базовый образ — по минорной версии.
FROM caddy:2.11-builder AS builder
# --replace поднимает библиотеки, в которых trivy image нашёл HIGH/CRITICAL
# (x/crypto CVE-2026-56854 и др., SFR-4b): фикс в самих библиотеках вышел,
# но Caddy 2.11.4 их ещё не подтянул, а собираем бинарь мы сами. Пересмотр —
# при обновлении Caddy: если апстрим догнал версии, строки убрать.
RUN xcaddy build \
    --with github.com/mholt/caddy-ratelimit@5625512f24f6f59d6f64fb3aafe5eecff0b286db \
    --replace golang.org/x/crypto=golang.org/x/crypto@v0.55.0 \
    --replace golang.org/x/net=golang.org/x/net@v0.56.0 \
    --replace golang.org/x/text=golang.org/x/text@v0.39.0 \
    --replace google.golang.org/grpc=google.golang.org/grpc@v1.83.1

FROM caddy:2.11

# Образ caddy пересобирается реже, чем выходят патчи Alpine: на 05.09.2026 в
# нём 23 HIGH-CVE (curl, c-ares, openssl) — все с доступным фиксом (trivy
# image, SFR-4b). apk upgrade подтягивает их на сборке.
RUN apk upgrade --no-cache

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
COPY Caddyfile /etc/caddy/Caddyfile

# Не root (trivy DS-0002). Прокси — единственный контейнер, смотрящий в
# интернет, поэтому здесь это важнее, чем для api и web (их обезроутили
# в SFR-4). Официальный образ Caddy рассчитан на root, но документация
# описывает и запуск от пользователя; нужны две вещи:
#   * cap_net_bind_service — иначе не занять 80/443 на бою (на локальной
#     репетиции прокси слушает 8080 и капабилити не задействована);
#   * права на /data (сертификаты автоTLS, access-лог) и /config — именно
#     с этих каталогов docker снимает владельца при СОЗДАНИИ именованного
#     тома. Уже существующие тома остаются root'овыми: при обновлении
#     работающего стенда их надо пересоздать (deploy/README.md).
RUN setcap cap_net_bind_service=+ep /usr/bin/caddy \
    && addgroup -g 10001 caddy \
    && adduser -D -H -u 10001 -G caddy caddy \
    && chown -R caddy:caddy /data /config
# uid зафиксирован строкой adduser выше; имя читается лучше числа.
# hadolint ignore=DL3066
USER caddy
