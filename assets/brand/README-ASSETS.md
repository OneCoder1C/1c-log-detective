# 1C Log Detective — brand assets

## Files
- `logo-full.svg` — основной логотип с названием и подписью.
- `logo-symbol.svg` — отдельный знак в SVG.
- `icon-512.png`, `icon-256.png`, `icon-64.png` — иконки для интерфейса и отчёта.
- `favicon.ico`, `favicon-32.png`, `favicon-16.png` — значок браузера.
- `github-readme-banner.svg` — баннер для README GitHub.

## Рекомендуемая палитра
- Navy: `#061B33`
- Deep blue: `#09294A`
- Blue: `#08A9F4`
- Cyan: `#36D0FF`
- Incident orange: `#FF9D00`
- White: `#F4F8FC`

## Подключение favicon
Положите `favicon.ico` рядом с HTML-файлом и добавьте в `<head>`:
```html
<link rel="icon" href="favicon.ico" sizes="any">
```

## Подключение логотипа в HTML-отчёте
Положите `logo-symbol.svg` или `icon-64.png` рядом с отчётом. Для автономного HTML лучше встроить SVG/PNG в HTML как data URI, чтобы отчёт оставался одним файлом.

## README GitHub

Баннер уже находится в `assets/brand/`. Для подключения в корневом README.md используйте:

```markdown
![1C Log Detective](assets/brand/github-readme-banner.svg)
```

Это первая рабочая версия фирменного стиля. Перед массовым использованием стоит проверить читаемость иконки на реальном размере 16×16 и согласовать её с текущей шапкой HTML-отчёта.
