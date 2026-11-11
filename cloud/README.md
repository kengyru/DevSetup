# DevSetup Cloud Backend

Standalone Django/DRF service that stores user `.setup` files for the
DevSetup desktop application. The backend only **validates and stores**
data. It never executes anything from a setup file: no `subprocess`,
no `winget`, `pip`, `npm`, `git` or `wsl` calls exist in this codebase.

The desktop application is a separate project in `../app` and is not
imported or modified by this service.

---

## 1. Requirements

| Component | Version |
| --- | --- |
| Python | 3.12+ (tested with 3.13) |
| Django | 5.2 LTS (`5.2.18`) |
| Django REST Framework | 3.16 (`3.16.1`) |
| SimpleJWT | 5.5 (`5.5.1`) |
| PostgreSQL | 14+ (tested with 17.6) |
| psycopg | 3.3 (`3.3.6`) |

SQLite is intentionally **not** supported, neither in development nor in
production.

---

## 2. Project layout

```
cloud/
├── manage.py
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
├── conftest.py
├── .env.example
├── .gitignore
├── README.md
├── config/
│   ├── settings.py          # production-minded settings
│   ├── settings_test.py     # isolated test database + fast hashing
│   ├── urls.py
│   ├── middleware.py        # request body size guard
│   ├── exceptions.py        # generic 500 responses
│   ├── asgi.py
│   └── wsgi.py
├── accounts/
│   ├── models.py            # custom email-based User
│   ├── serializers.py       # registration + email login
│   ├── views.py             # register / login / refresh
│   ├── urls.py
│   ├── admin.py
│   ├── migrations/
│   └── tests/test_auth.py
└── setups/
    ├── models.py            # Setup (UUID, JSON, owner)
    ├── schema.py            # independent validation & sanitisation
    ├── security.py          # name-based secret detection
    ├── serializers.py       # API serializers + 50 setup limit
    ├── views.py             # owner-filtered ViewSet
    ├── urls.py
    ├── admin.py
    ├── migrations/
    └── tests/
        ├── test_api.py
        ├── test_authorization.py
        ├── test_validation.py
        ├── test_schema.py
        ├── test_security.py
        └── test_settings.py
```

---

## 3. Virtual environment and dependencies

```powershell
cd cloud
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Production dependencies
python -m pip install -r requirements.txt

# Test tooling (pytest, pytest-django)
python -m pip install -r requirements-dev.txt
```

On Linux/macOS use `source .venv/bin/activate` instead.

---

## 4. PostgreSQL

Create a dedicated role and database. The role needs `CREATEDB` so the
test suite can create and destroy its own database.

```sql
CREATE ROLE devsetup LOGIN CREATEDB PASSWORD 'change-me';
CREATE DATABASE devsetup OWNER devsetup;
```

Using `psql`:

```powershell
psql -h 127.0.0.1 -p 5432 -U postgres -c "CREATE ROLE devsetup LOGIN CREATEDB PASSWORD 'change-me';"
psql -h 127.0.0.1 -p 5432 -U postgres -c "CREATE DATABASE devsetup OWNER devsetup;"
```

The server must listen on the host/port configured in `.env`
(`127.0.0.1:5432` by default).

---

## 5. Environment variables

Copy the example file and edit it. `.env` is git-ignored and must never
be committed.

```powershell
Copy-Item .env.example .env
```

| Variable | Meaning |
| --- | --- |
| `DJANGO_SECRET_KEY` | Long random string; required, no default |
| `DJANGO_DEBUG` | `False` by default; enable only locally |
| `DJANGO_ALLOWED_HOSTS` | Comma separated host names |
| `DJANGO_LOG_LEVEL` | Root log level (`INFO` by default) |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | PostgreSQL connection |
| `DB_CONN_MAX_AGE` | Persistent connection lifetime in seconds |
| `DB_SSLMODE` | `prefer`, `require`, ... |
| `CORS_ALLOWED_ORIGINS` | Explicit list of allowed browser origins |
| `CORS_ALLOW_ALL_ORIGINS` | Must stay `False` in production |
| `DJANGO_SECURE_SSL_REDIRECT` | Redirect HTTP to HTTPS |
| `DJANGO_SECURE_HSTS_SECONDS` | HSTS max-age; `0` disables HSTS |
| `DJANGO_SESSION_COOKIE_SECURE`, `DJANGO_CSRF_COOKIE_SECURE` | Secure cookies |
| `AUTH_THROTTLE_RATE` | Rate for register/login/refresh (`10/min`) |
| `MAX_REQUEST_BYTES` | Hard HTTP body limit for setup writes (4 MB) |

The service refuses to start in production (`DEBUG=False`) if
`DJANGO_SECRET_KEY` still contains the example placeholder, and it
refuses `CORS_ALLOW_ALL_ORIGINS=True` outside debug mode.

---

## 6. Migrations

```powershell
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py migrate
```

Migrations create:

* `accounts_user` — custom user, case-insensitive unique email;
* `setups_setup` — UUID primary key, owner FK, name, format version,
  JSON data, timestamps, index on `(user, -created_at)`, check
  constraint allowing only format versions 1 and 2;
* Django/SimpleJWT tables (`token_blacklist_*`, etc.).

---

## 7. Run the server

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Health check:

```powershell
curl http://127.0.0.1:8000/api/setups/
# 401 Unauthorized without a token
```

---

## 8. Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

* settings module: `config.settings_test`;
* database: fixed name `test_devsetup` (created/destroyed by
  pytest-django), never the real `devsetup` database;
* fast password hashing and a high throttle rate are used only in tests;
* the throttle implementation itself is covered by a dedicated test
  that lowers the rate to `2/min`.

The PostgreSQL role must have `CREATEDB`; otherwise the test database
cannot be created.

Current result: **112 passed**.

---

## 9. API

All setup endpoints require a JWT access token:

```
Authorization: Bearer <access_token>
```

### 9.1 Register

`POST /api/auth/register/`

```json
{
  "email": "alice@example.com",
  "password": "ValidPass!2345"
}
```

`201 Created`

```json
{
  "id": 1,
  "email": "alice@example.com",
  "created_at": "2026-10-30T15:00:00Z"
}
```

Errors: `400` for an invalid email, weak password or duplicate email
(case-insensitive). The password hash is never returned.

### 9.2 Login

`POST /api/auth/login/`

```json
{
  "email": "alice@example.com",
  "password": "ValidPass!2345"
}
```

`200 OK`

```json
{
  "access": "<jwt access token, 15 minutes>",
  "refresh": "<jwt refresh token, 7 days>"
}
```

Errors: `401` for wrong credentials, `429` when the auth throttle is
exceeded.

### 9.3 Refresh

`POST /api/auth/refresh/`

```json
{
  "refresh": "<refresh token>"
}
```

`200 OK`

```json
{
  "access": "<new access token>",
  "refresh": "<rotated refresh token>"
}
```

Refresh rotation and blacklisting are enabled: the old refresh token
cannot be reused (`401`).

### 9.4 Create setup

`POST /api/setups/`

```json
{
  "name": "Workstation",
  "data": {
    "format_version": 2,
    "applications": [
      {
        "name": "Git",
        "version": "2.45.0",
        "path": "C:\\Program Files\\Git",
        "installed": true,
        "package_id": "Git.Git"
      },
      {
        "name": "VS Code",
        "version": "1.90.0",
        "installed": true,
        "package_id": "Microsoft.VisualStudioCode",
        "extensions": ["ms-python.python"]
      }
    ],
    "git_config": {
      "user.name": "Alice",
      "user.email": "alice@example.com"
    },
    "python_packages": ["Django==5.2.4"],
    "npm_packages": ["typescript"],
    "wsl_distributions": [{"name": "Ubuntu", "version": 2}],
    "environment_variables": {"NODE_ENV": "development"},
    "secret_environment_variables": ["NPM_TOKEN"],
    "terminal": {
      "available": true,
      "profiles": ["Windows.Terminal.PowershellCore"]
    }
  }
}
```

`201 Created` returns the stored (sanitised) object:

```json
{
  "id": "0f0f0f0f-1111-4222-8333-444455556666",
  "name": "Workstation",
  "format_version": 2,
  "data": {
    "applications": [
      {
        "name": "Git",
        "version": "2.45.0",
        "path": "C:\\Program Files\\Git",
        "installed": true,
        "package_id": "Git.Git"
      },
      {
        "name": "VS Code",
        "version": "1.90.0",
        "path": null,
        "installed": true,
        "package_id": "Microsoft.VisualStudioCode",
        "extensions": ["ms-python.python"]
      }
    ],
    "git_config": {
      "user.email": "alice@example.com",
      "user.name": "Alice"
    },
    "python_packages": ["Django==5.2.4"],
    "npm_packages": ["typescript"],
    "wsl_distributions": [{"name": "Ubuntu", "version": 2}],
    "environment_variables": {"NODE_ENV": "development"},
    "secret_environment_variables": ["NPM_TOKEN"],
    "terminal": {
      "available": true,
      "settings_path": null,
      "default_profile": null,
      "profiles": ["Windows.Terminal.PowershellCore"],
      "font_face": null,
      "color_scheme": null,
      "message": null
    }
  },
  "created_at": "2026-10-30T15:01:00Z",
  "updated_at": "2026-10-30T15:01:00Z"
}
```

`format_version` is always derived from `data.format_version`; a
top-level `format_version` in the request is ignored. Missing
`data.format_version` means version 1 (desktop compatibility).

Errors: `400` for invalid payloads / limits, `413` for bodies above
4 MB, `401` without a token, `429` when throttled.

### 9.5 List setups

`GET /api/setups/`

`200 OK` — only metadata, never `data`:

```json
[
  {
    "id": "0f0f0f0f-1111-4222-8333-444455556666",
    "name": "Workstation",
    "format_version": 2,
    "created_at": "2026-10-30T15:01:00Z",
    "updated_at": "2026-10-30T15:01:00Z"
  }
]
```

Only the authenticated user's setups are returned, newest first.

### 9.6 Retrieve setup

`GET /api/setups/{uuid}/`

`200 OK` — same shape as the create response (includes `data`).

`404` for a missing **or foreign** setup.

### 9.7 Update setup

`PUT /api/setups/{uuid}/`

```json
{
  "name": "Workstation (updated)",
  "data": {
    "format_version": 2,
    "applications": []
  }
}
```

Full replacement; `PATCH` is not exposed (`405`). The same validation
and limits apply. `404` for a foreign setup.

### 9.8 Delete setup

`DELETE /api/setups/{uuid}/`

`204 No Content`. `404` for a foreign setup.

---

## 10. Validation rules

Accepted versions: **1** and **2**; missing means **1**; anything else
is rejected.

* payload must be a JSON object ≤ **2 MB**;
* nested depth ≤ 8, every object ≤ 1 000 keys, every array ≤ 1 000
  items, ≤ 20 000 values in total;
* name ≤ 100 characters (trimmed, not blank), ≤ 50 setups per user;
* applications ≤ 100, extensions per app ≤ 300, Python/npm packages
  ≤ 500 each, WSL distributions ≤ 50, Git settings ≤ 100, environment
  variables ≤ 200, terminal profiles ≤ 100;
* unknown fields are dropped, not stored;
* Git settings outside the desktop allowlist are dropped;
* pip entries must be `name==version`; options, URLs, git references,
  editable installs and shell metacharacters are dropped;
* npm names must match the npm name grammar;
* extension IDs, WSL names and environment variable names are checked;
* environment variables whose **name** looks secret are never stored as
  values — only their names are recorded in
  `secret_environment_variables`;
* system-managed variables (`PATH`, `USERPROFILE`, ...) are dropped;
* NUL characters, non-string values and over-long strings are dropped
  or rejected as appropriate.

Version 1 setups store only `applications`, matching the desktop
importer.

---

## 11. Security

* JWT access tokens: 15 minutes; refresh tokens: 7 days; rotation and
  blacklist enabled;
* `DEBUG=False` by default;
* secrets only from environment variables / `.env` (git-ignored);
* `CORS_ALLOW_ALL_ORIGINS` must stay `False` outside debug mode;
* HTTPS-ready switches (`SECURE_SSL_REDIRECT`, HSTS, secure cookies,
  `SECURE_PROXY_SSL_HEADER`);
* throttling on register/login/refresh (`10/min` by default);
* every queryset is filtered by `request.user`; foreign resources
  return `404`;
* generic `500` responses — no tracebacks, SQL or request bodies;
* passwords are hashed with Django's hashers and never returned;
* passwords, access/refresh tokens and secret values are never logged;
* no OAuth, email verification or password reset in this stage.

**The API never executes setup content.** There are no process
execution calls anywhere in `accounts/`, `setups/` or `config/`, and a
test asserts this by monkeypatching `subprocess` and `os.system`.

---

## 12. Known limitations

* No desktop API client, cloud UI, OAuth, email verification or
  password reset yet.
* No Docker/VPS deployment, Redis or Celery.
* Throttling uses the local-memory cache; a multi-process deployment
  needs a shared cache (for example Redis) for exact counters.
* A single request body is capped at 4 MB, the setup payload at 2 MB;
  setups are stored in PostgreSQL as JSONB.
* `PATCH` is not supported; updates are full `PUT` replacements.
* No file storage or project archive backup — only the JSON `.setup`
  document.
