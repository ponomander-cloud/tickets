# RZD live coupe finder

Live, coupe-only RZD search powered by `rzd-api==3.0.0`.

## Vercel HTTP API

Deploy the repository to Vercel and call:

```text
GET /api/search?from=Москва&to=Адлер&date_from=2026-08-15&days=14&top_per_day=3&overall_top=10
```

The endpoint does not read `request.json`. It returns one cheapest coupe offer per train and date,
plus `overall_cheapest` and normalized `overall_value` rankings. `request.json` remains only for the
optional batch workflow that writes `data/latest.json`.

Собирает живые данные `ticket.rzd.ru` через `rzd-api` и сохраняет результат в `data/latest.json`.

## Формат результата

- только **купе**;
- диапазон 1–31 день;
- `top_coupe`: самые дешёвые варианты на каждый день;
- для каждого варианта: цена, поезд, отправление, прибытие, длительность, количество мест;
- `overall_top`: общий рейтинг самых дешёвых купе по всему диапазону.

## Изменить запрос

Отредактируй `request.json`:

```json
{
  "from": "Москва",
  "to": "Адлер",
  "date_from": "2026-08-15",
  "days": 14,
  "top_per_day": 3,
  "overall_top": 10
}
```

После push изменения `request.json` GitHub Action запустится автоматически. Также его можно запустить вручную: **Actions → Fetch live RZD coupe prices → Run workflow**.

Итог находится в `data/latest.json`.
