# DevSetup

DevSetup — локальное Windows-приложение, которое сохраняет конфигурацию
рабочего окружения разработчика в файл `.setup` и восстанавливает её на этом
же или другом компьютере.

Работает без аккаунтов, серверов, облака и базы данных.

## Что умеет

### Приложения

- **Scan PC** — находит Python, Git, VS Code, Docker, PostgreSQL: версию,
  путь, признак установки и `winget` package id.
- **Save Setup** — сохраняет окружение в обычный JSON-файл `.setup`.
- **Import Setup** — загружает `.setup`, заново сканирует ПК и сравнивает
  желаемое состояние с фактическим.
- **Restore Setup** — устанавливает выбранные отсутствующие приложения через
  `winget`.
- **Version mismatch** — для установленного приложения с другой версией
  показывается `Saved / Current / Status` и кнопка **[Restore Version]**.
  Версия восстанавливается только после подтверждения и только если
  `winget` реально предлагает её. Иначе показывается:
  `Required version is not available through winget.`

### Инструменты разработчика

- **VS Code extensions** — список через `code --list-extensions`, сохранение
  id расширений внутри записи VS Code, установка отсутствующих через
  `code --install-extension ID`.
- **Git config** — только безопасный allowlist: `user.name`, `user.email`,
  `core.editor`, `core.autocrlf`, `core.eol`, `init.defaultbranch`,
  `pull.rebase`, `pull.ff`, `push.default`, `push.autosetupremote`,
  `merge.conflictstyle`, `fetch.prune`. Credentials, aliases, URL rewrites и
  signing keys не сохраняются и не восстанавливаются.
- **Python global packages** — `pip freeze` глобального интерпретатора
  (venv автоматически разворачивается до базового Python). Восстановление
  одним `pip install -r` из временного файла.
- **npm global packages** — `npm list -g --depth=0`, имена пакетов,
  восстановление по одному через `npm install -g`.
- **WSL** — distributions и версия WSL (1/2) через `wsl --list --verbose`.
  Отсутствующую distribution можно предложить установить через
  `wsl --install -d NAME --no-launch` (обычно нужен UAC и возможна
  перезагрузка). Linux-файловая система **не** резервируется.
- **Environment variables** — безопасные пользовательские переменные из
  `HKCU\Environment`. Секреты определяются по имени переменной
  (`*_API_KEY`, `*_TOKEN`, `*_PASSWORD`, `*_SECRET`, `PRIVATE_KEY`,
  `ACCESS_KEY`, `AUTH*`, `CONNECTION_STRING` и т. п.) и **не сохраняются**.
  В UI и в `.setup` остаётся только имя со статусом
  `Secret — not backed up`.
- **Windows Terminal** — read-only обнаружение: default profile, профили,
  шрифт, color scheme. Автоматическое восстановление не выполняется, потому
  что GUID профилей и пути привязаны к конкретной машине.

## Требования

- Windows 10/11;
- Python 3.11+ (проект проверен на 3.13);
- `winget` (App Installer из Microsoft Store) — нужен только для Restore;
- `git`, `code`, `npm`, `wsl` — соответствующие разделы просто пропускаются,
  если инструмент не установлен;
- интернет для установки программ и пакетов.

## Запуск

```powershell
cd DevSetup
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Если `.venv` уже создан:

```powershell
.venv\Scripts\python.exe main.py
```

## Как пользоваться

1. Нажать **Scan PC**. Окно показывает окружение по категориям:
   Applications, VS Code Extensions, Packages, Configuration, WSL, Terminal.
2. Нажать **Save Setup**, ввести имя и выбрать путь — получится `name.setup`.
3. На другом ПК нажать **Import Setup** и выбрать файл.
4. DevSetup покажет сравнение:
   - `✓ Installed` — всё совпадает;
   - `✗ Missing` — элемента нет;
   - `⚠ Version mismatch` — версия отличается; рядом кнопка
     **[Restore Version]**.
5. Нажать **Restore Setup**. Откроется диалог с checkbox-ами по категориям.
   По умолчанию включены приложения, расширения, пакеты и Git config;
   смена версии, переменные окружения и WSL выключены и требуют явного
   выбора.
6. Нажать **Restore Selected**, затем подтвердить итоговый список.
   Если выбрать **No** или снять все checkbox-и, не выполняется ничего.
7. После восстановления DevSetup сам повторяет скан и показывает итог.

Все длительные операции (`winget`, `pip`, `npm`, `code`, `wsl`) выполняются
в фоновом потоке; строка статуса показывает текущий шаг
(`Scanning Python packages...`, `Installing VS Code extensions...`,
`Restoring Python packages...` и т. п.).

## Формат `.setup`

Файл — обычный JSON. Текущий формат — версия 2.

```json
{
    "format_version": 2,
    "name": "backend",
    "applications": [
        {
            "name": "VS Code",
            "version": "1.143.1",
            "path": "C:\\VSCode\\bin\\code.cmd",
            "installed": true,
            "package_id": "Microsoft.VisualStudioCode",
            "extensions": [
                "ms-python.python",
                "ms-python.vscode-pylance"
            ]
        },
        {
            "name": "Docker",
            "version": "Not installed",
            "path": null,
            "installed": false,
            "package_id": "Docker.DockerDesktop"
        }
    ],
    "git_config": {
        "user.name": "Ann",
        "user.email": "ann@example.test"
    },
    "python_packages": [
        "Django==5.2.4",
        "requests==2.32.3"
    ],
    "npm_packages": [
        "typescript"
    ],
    "wsl_distributions": [
        {
            "name": "Ubuntu",
            "version": 2,
            "state": "Running"
        }
    ],
    "environment_variables": {
        "EDITOR": "code --wait"
    },
    "secret_environment_variables": [
        "OPENAI_API_KEY"
    ],
    "terminal": {
        "available": true,
        "settings_path": "C:\\Users\\dev\\...\\settings.json",
        "default_profile": "PowerShell",
        "profiles": ["PowerShell", "Ubuntu"],
        "font_face": "Cascadia Code",
        "color_scheme": "Campbell",
        "message": null
    }
}
```

### Совместимость

- Файлы с `format_version: 1` (и файлы без `format_version`, созданные
  первым MVP) импортируются как версия 1. В них есть только приложения.
- Новые файлы всегда пишутся как версия 2.
- Значения неизвестных/будущих версий формата отклоняются.

### Безопасность формата

- `package_id` из файла считается недостоверным. При восстановлении
  `winget` id берётся только из локального allowlist в
  `app/core/packages.py`.
- Python-пакеты принимаются только в виде `name==version`. Опции pip,
  URL, git-ссылки, локальные пути и editable-установки отбрасываются.
- npm-пакеты и WSL distributions проверяются регулярными выражениями.
- Git-настройки проходят allowlist.
- Переменные окружения проверяются по имени; секреты и системные
  переменные (`PATH`, `TEMP`, `USERPROFILE`, ...) не сохраняются.
- Никакая команда из `.setup` не выполняется через shell. Все внешние
  команды запускаются списком аргументов, без `shell=True`.

## Package id, используемые при восстановлении

| Приложение | winget id |
|---|---|
| Python | `Python.Python.3.13` |
| Git | `Git.Git` |
| VS Code | `Microsoft.VisualStudioCode` |
| Docker | `Docker.DockerDesktop` |
| PostgreSQL | `PostgreSQL.PostgreSQL` |

## Тесты

```powershell
.venv\Scripts\python.exe -m unittest discover -s test -v
```

Покрыто:

- сравнение окружения и version mismatch;
- импорт v1 и v2, повреждённые файлы;
- фильтрация секретов и небезопасных записей;
- VS Code extensions, Git config, pip/npm-пакеты, WSL (включая UTF-16),
  environment variables, terminal JSONC;
- version restore: точная версия, недоступная версия, таймаут;
- restore Yes/No на уровне оркестрации и UI-диалога;
- отсутствующие `npm`, `wsl`, `python`, `git`, `winget`;
- изоляция ошибок сканеров и сборщиков.

Автоматические тесты **не устанавливают** реальные программы: все внешние
команды замокированы. В тестах 108 проверок.

## Структура

```
main.py                          — точка входа, тема, обработка ошибок
app/models/                      — Setup, EnvironmentSnapshot, comparison, restore
app/scanner/                     — приложения + extensions, git config,
                                   pip/npm, WSL, environment, terminal
app/services/                    — scan, compare, restore, extensions, packages,
                                   config, WSL, environment restore
app/backup/                      — экспорт и импорт .setup (v1/v2)
app/ui/                          — MainWindow, ApplicationCard, SummaryCard,
                                   RestoreDialog, фоновый Task
app/core/                        — package id, версии, секреты, валидаторы,
                                   запуск процессов
test/                            — unittest-тесты
```

## Ограничения

- **Terminal** — только read-only. Полное восстановление `settings.json`
  между машинами небезопасно: GUID профилей, starting directory и пути
  привязаны к системе.
- **WSL** — сохраняются только имена distributions и версия WSL. Linux
  filesystem, пользовательские файлы и настройки внутри WSL не
  резервируются. Установка distribution может требовать UAC и
  перезагрузки; `wsl --install` может не поддерживаться старой версией WSL.
- **Environment variables** — определение секретов основано на имени
  переменной. Переменная с неожиданным именем и секретным значением может
  быть сохранена; переменная с «секретным» именем будет пропущена даже если
  значение безопасно. Изменения видны новым процессам; уже запущенные
  приложения могут не подхватить их без перезапуска.
- **Git config** — восстанавливается только allowlist. Credentials, SSH
  keys, aliases и URL rewrites не сохраняются.
- **Python** — только глобальное окружение, не пакеты конкретного venv.
- **npm** — сохраняются только имена пакетов, без версий.
- **Version restore** — только через `winget` и только точное совпадение
  строки версии. Например, Git может сообщать `2.56.0.windows.2`, а winget
  использовать `2.56.0.2`; в этом случае DevSetup честно покажет
  `Required version is not available through winget.` и ничего не изменит.
- **VS Code** — сохраняются extensions, но не пользовательские settings,
  keybindings и snippets.
- Docker Desktop и PostgreSQL могут требовать прав администратора (UAC) и
  перезагрузки — это поведение их установщиков.
- Приложение Windows-only: используются `winget`, `cmd`, `winreg` и
  `%LOCALAPPDATA%`.

## Если что-то не работает

- **«winget was not found»** — установите App Installer из Microsoft Store,
  проверьте `winget --version`.
- **«npm is not installed» / «WSL is not installed»** — соответствующий
  раздел пропускается; установите Node.js/WSL и повторите Scan PC.
- **Version mismatch не восстанавливается** — winget не предлагает точную
  сохранённую версию. Обновите/установите вручную либо сохраните setup с
  версией, которая есть в winget.
- **Restore завершился с ошибкой** — текст ошибки показывается в диалоге;
  частые причины: отмена UAC, отсутствие сети, неизвестный package id.
- **Не закрывается окно** — дождитесь окончания фоновой задачи, чтобы не
  оборвать `winget`, `pip` или `npm`.
