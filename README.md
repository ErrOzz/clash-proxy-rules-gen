# clash-proxy-rules-gen

Краткое описание

`clash-proxy-rules-gen` — простой инструмент для генерации провайдера правил для Clash из текстового списка.

Назначение

Инструмент читает `rules/rules_proxy` (по одной записи на строку), фильтрует комментарии и пустые строки и преобразует каждую запись в запись формата, подходящую для Clash Rule Provider. Результат сохраняется в `clash_proxy_rules.yaml`.

Основные возможности

- Поддержка доменов, wildcard-доменов, IP/CIDR и ключевых слов.
- Выдача результата в формате `payload:` для использования в Clash.
- Автоматический запуск через GitHub Actions при изменении исходного списка правил.

Быстрый старт

1. Клонируйте репозиторий и откройте терминал в корне проекта.
2. Выполните генерацию локально:

```bash
cd scripts
rm -f ../clash_proxy_rules.yaml
bash deploy.sh
```

После выполнения в корне появится `clash_proxy_rules.yaml`.

Структура репозитория

- `rules/rules_proxy` — входной список правил.
- `scripts/deploy.sh` — скрипт генерации.
- `clash_proxy_rules.yaml` — сгенерированный файл.
- `.github/workflows/main.yml` — автоматический запуск при изменениях правил.
- `.github/workflows/test_deploy.yml` — ручной workflow для тестирования.

Формат правил в `rules/rules_proxy`

- Комментарии: строки, начинающиеся с `#`, игнорируются.
- Типы записей:
  - Домены: `example.com` или `*.example.com` → `DOMAIN-SUFFIX`
  - IP / CIDR: `1.2.3.0/24` → `IP-CIDR`
  - Ключевые слова: `youtube` → `DOMAIN-KEYWORD`

Пример `clash_proxy_rules.yaml`

```yaml
payload:
  - DOMAIN-SUFFIX,example.com
  - DOMAIN-KEYWORD,youtube
  - IP-CIDR,1.2.3.0/24
```