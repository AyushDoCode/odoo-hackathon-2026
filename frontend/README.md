# AssetFlow by odoo — Frontend

The static frontend for **AssetFlow by odoo**: login/signup plus the full app
(dashboard, assets, allocation & transfer, resource booking, maintenance,
audit, reports, organization setup, notifications). Plain HTML/CSS/JS, no
build step.

This directory is served directly by the backend (`app/main.py` mounts it at
`/` — see the top-level `../README.md`), so there's nothing to run here on its
own; start the backend and open `http://localhost:8000/`.

## Tech Stack

- HTML5
- CSS3 (variables, in `assets/pages.css` for the app shell and `assets/style.css`
  for login/signup)
- Vanilla JavaScript — `assets/api.js` is the shared API client every page's
  inline script calls into (auth, fetch wrapper, session storage)

## Files

- `index.html` / `signup.html` — auth pages.
- `dashboard.html`, `assets-directory.html`, `allocation-transfer.html`,
  `resource-booking.html`, `maintenance.html`, `audit.html`,
  `organization-setup.html`, `reports.html`, `notifications.html` — the app,
  each wired to its corresponding `/api/...` routes.
- `assets/api.js` — shared API client (`window.AssetFlowAPI`).
- `assets/style.css`, `assets/pages.css` — styles and CSS variables.
- `assets/images/`, `assets/icons/` — SVG assets.

```
    _                    _   _____   _
   / \    ___  ___  ___ | |_|  ___| | |  ___  __      __
  / _ \  / __|/ __|/ _ \| __| |_    | | / _ \ \ \ /\ / /
 / ___ \ \__ \\__ \  __/| |_|  _|   | || (_) | \ V  V /
/_/   \_\|___/|___/\___| \__|_|     |_| \___/   \_/\_/
```

`AssetFlow by odoo`
