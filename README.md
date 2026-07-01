# kalender.py

A terminal calendar (powered by [`rich`](https://github.com/Textualize/rich)) that shows a full-year grid with public holidays, bank holidays, school holidays, observances, and custom company day-offs highlighted.

Holiday data comes from the free **[Nager.Date](https://date.nager.at) public holiday API** — no API key needed, 100+ countries supported — and is cached locally so the tool still works offline. Every day type can also be added, removed, and overridden by hand through the `.ini` config file, either globally or scoped to a specific country.

```
╭──────────────────────────────────────────────────────────────────────╮
│ Year 2026 — Country: ID                                              │
╰──────────────────────────────────────────────────────────────────────╯
 January 2026          February 2026         March 2026          April 2026
 Mo Tu We Th Fr Sa Su  Mo Tu We Th Fr Sa Su  Mo Tu We Th Fr Sa Su  Mo Tu We Th Fr Sa Su
           1  2  3  4                   1                   1         1  2  3  4  5
  5  6  7  8  9 10 11   2  3  4  5  6  7  8   2  3  4  5  6  7  8   6  7  8  9 10 11 12
 12 13 14 15 16 17 18   9 10 11 12 13 14 15   9 10 11 12 13 14 15  13 14 15 16 17 18 19
 19 20 21 22 23 24 25  16 17 18 19 20 21 22  16 17 18 19 20 21 22  20 21 22 23 24 25 26
 26 27 28 29 30 31     23 24 25 26 27 28     23 24 25 26 27 28 29  27 28 29 30
                                             30 31

 Holidays and Days Off:            Holidays and Days Off:
 • 1: New Year's Day (Public)
```

---

## Features

- **Full-year grid view** — 4 months per row, all columns locked to equal width regardless of how long the holiday legend text is. Current day blinks. Weekends are colored.
- **Online holiday data** for 100+ countries via Nager.Date — fetched automatically and cached locally (no API key required).
- **Offline-friendly** — falls back to the local JSON cache or your config file if there's no network.
- **7 day types**, each with its own color in the grid and the legend:

  | Type          | Config section  | Color (cell)              | Meaning                            |
  |---------------|-----------------|---------------------------|------------------------------------|
  | `public`      | `[holidays]`    | cyan on red               | National / public holidays         |
  | `bank`        | `[bank]`        | black on orange           | Bank holidays                      |
  | `school`      | `[school]`      | black on teal             | School holidays                    |
  | `authorities` | `[authorities]` | white on blue             | Government / authority holidays    |
  | `optional`    | `[optional]`    | black on grey             | Optional holidays                  |
  | `observance`  | `[observance]`  | black on yellow           | Observances (noted, not a day off) |
  | `dayoff`      | `[dayoffs]`     | black on magenta          | Custom / company day-offs          |

- **Full CRUD from the CLI** for any day type — `add`, `remove`, `list`.
- **Per-country scoping** — add or remove a day for one specific country without affecting any other, or leave it global so it appears for every country.
- **Exclude specific API dates** — suppress a Nager.Date-fetched holiday you don't want shown, per country or globally.
- **Local JSON cache** with a configurable TTL so you're not hitting the API on every run.

---

## Requirements

```bash
pip install rich configset requests
```

| Package      | Required | Purpose                                                |
|--------------|----------|--------------------------------------------------------|
| `rich`       | yes      | Terminal rendering                                     |
| `configset`  | yes      | `.ini` config parsing                                  |
| `requests`   | no       | Online holiday fetching — tool still works without it  |
| `pydebugger` | no       | Debug tracing — no-ops gracefully if absent            |

---

## Quick start

```bash
# Current year, default country (ID unless you've changed it)
python3 kalender.py

# Specific year and country
python3 kalender.py -y 2026 -c US

# Use config/cache only, no network call
python3 kalender.py --no-fetch

# Ignore cache, force a fresh online fetch
python3 kalender.py --refresh -c DE

# Persist a default country so you don't have to pass -c every time
python3 kalender.py set-country ID
```

---

## Managing day entries

### Add

```bash
kalender.py add <type> <YYYY-MM-DD> "<name>" [-c COUNTRY]
```

```bash
# Global — shows up for every country
kalender.py add dayoff 2026-09-23 "Company Day Off"

# Scoped to Indonesia only
kalender.py add dayoff 2026-09-23 "Company Day Off" -c ID

# Scoped to United States only
kalender.py add bank 2026-12-24 "Christmas Eve" -c US

# Scoped to Indonesia only
kalender.py add bank 2026-08-17 "Kemerdekaan Eve" -c ID
```

Without `-c`, the entry goes into the type's global section (e.g. `[dayoffs]`) and applies everywhere. With `-c`, it goes into a country-specific section (e.g. `[bank_US]`) and only shows when viewing that country.

### Remove

```bash
kalender.py remove <type> --date <YYYY-MM-DD> [-c COUNTRY]
kalender.py remove <type> --key <config_key>  [-c COUNTRY]
```

```bash
# Remove the global dayoff entry
kalender.py remove dayoff --date 2026-09-23

# Remove only the US-scoped bank holiday
kalender.py remove bank --date 2026-12-24 -c US
```

When `-c` is given, the country-specific section is checked first. If no match is found there, it falls back to the global section — so `remove ... -c US` will remove a global entry if no US-specific one exists for that date.

### Exclude an API-fetched holiday

Suppress a date that Nager.Date returns but you don't want to show, without adding your own manual entry for it:

```bash
# Suppress globally (no country = every country)
kalender.py exclude 2026-01-06 --name "Epiphany"

# Suppress only for Germany
kalender.py exclude 2026-01-06 --name "Epiphany" -c DE
```

Excluded dates are stored in `[excluded]` (global) or `[excluded_DE]` (country-specific) in the config file.

### List

```bash
kalender.py list                    # all types for the current year
kalender.py list public             # just public holidays
kalender.py -y 2026 -c US list all  # everything for US 2026
kalender.py -c ID list dayoff       # custom day-offs for Indonesia
```

### Country codes

```bash
kalender.py countries               # print every code Nager.Date supports
kalender.py set-country DE          # persist a new default country
```

---

## Command reference

```
usage: kalender.py [-y YEAR] [-c COUNTRY] [--no-fetch] [--refresh] [COMMAND]

Global options
  -y, --year YEAR       Year to display/operate on (default: current year)
  -c, --country CODE    ISO 3166-1 alpha-2 code, e.g. ID, US, DE, JP
                        (default: value from [settings] country, fallback ID)
  --no-fetch            Skip the online API call; use config/cache only
  --refresh             Delete cached data and force a fresh online fetch

Commands
  (none)                         Show the full-year grid
  add TYPE DATE NAME [-c]        Add a day entry to the config
  remove TYPE [--date|--key] [-c] Remove a day entry from the config
  exclude DATE [--name] [-c]     Suppress an API-fetched date
  list [TYPE]                    List days for the selected year/country
  countries                      List all Nager.Date country codes
  set-country CODE               Persist a new default country
```

`-c` can appear before or after the subcommand — both are equivalent:

```bash
kalender.py -c US list bank
kalender.py list bank -c US
```

---

## Config file (`kalender.ini`)

Created automatically next to `kalender.py` the first time you run `add`, `set-country`, or any write operation. You can also create or edit it by hand — it's a plain INI file.

### Format

Each entry is stored as:

```ini
key_name = year,month,day
```

The key is the day name lowercased with spaces replaced by underscores. Example:

```ini
[dayoffs]
company_day_off = 2026,9,23

[bank_US]
christmas_eve = 2026,12,24

[bank_ID]
kemerdekaan_eve = 2026,8,17
```

### Full annotated example

```ini
[settings]
country    = ID    ; default country when -c is not given
auto_fetch = 1     ; 1/true/yes/on = fetch online; 0/false/no/off = config+cache only
cache_days = 30    ; days before the local JSON cache is considered stale

; ── Global entries (apply to every country) ─────────────────────────────────

[holidays]
; public holidays you've added by hand, globally

[bank]
; bank holidays, globally

[school]
; school holidays, globally

[authorities]
; authority/government holidays, globally

[optional]
; optional holidays, globally

[observance]
; observances, globally

[dayoffs]
company_day_off = 2026,9,23

[excluded]
; dates from the online API you want hidden everywhere

; ── Country-scoped entries ──────────────────────────────────────────────────
; Section name = <global section name>_<COUNTRY CODE>

[bank_US]
christmas_eve = 2026,12,24

[bank_ID]
kemerdekaan_eve = 2026,8,17

[excluded_DE]
epiphany = 2026,1,6
```

### Merge order

For any day type and country (e.g. `bank` + `US`):

1. Global section (`[bank]`) is loaded first.
2. Country-specific section (`[bank_US]`) is merged on top — same-date entries in the country section override the global one.
3. Online API results are merged last and **never override a manually configured entry**.

So manual config always wins over the API, and country-specific entries always win over global ones on the same date.

---

## Caching

Cache files are stored next to the script as:

```
.kalender_cache_<COUNTRY>_<YEAR>.json
```

They're considered fresh for `cache_days` (default: 30 days). Options:

```bash
# Use the cache as normal (default)
python3 kalender.py -c ID

# Skip the network entirely, don't even check the cache age
python3 kalender.py --no-fetch

# Delete this year/country's cache and fetch fresh data
python3 kalender.py --refresh -c ID
```

---

## Color legend

| Day category          | Cell style                     |
|-----------------------|-------------------------------|
| Today                 | black on bright cyan, blinking |
| Public holiday        | cyan on red                   |
| Day off (custom)      | black on magenta              |
| Bank holiday          | black on orange               |
| School holiday        | black on teal                 |
| Authorities holiday   | white on blue                 |
| Optional holiday      | black on grey                 |
| Observance            | black on yellow               |
| Saturday              | yellow text                   |
| Sunday                | red text                      |
| Weekday               | cyan text                     |

When a date matches more than one type, the cell uses the highest-priority color (top of the table above), but all matching types are listed in the month legend below the grid.

---

## Nager.Date API

- Base URL: `https://date.nager.at/api/v3`
- Endpoint used: `GET /PublicHolidays/{year}/{countryCode}`
- No API key, no rate limit enforced.
- Returns holiday `types` per entry: `Public`, `Bank`, `School`, `Authorities`, `Optional`, `Observance` — these map directly to `kalender.py`'s day types.
- Coverage varies by country; Europe is the most complete. Run `kalender.py countries` to see what's available.

---

## Notes

- `Kalender.indonesian_holidays` and `Kalender.day_offs` class attributes are still populated (aliasing `public` and `dayoff` respectively) for backward compatibility with external code that imports this module directly.
- Set `TRACEBACK=1` in your environment to get full rich tracebacks on config parse errors.

---

## License

MIT — Hadi Cahyadi (cumulus13@gmail.com)

## 👤 Author
        
[Hadi Cahyadi](mailto:cumulus13@gmail.com)
    

[![Buy Me a Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/cumulus13)

[![Donate via Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/cumulus13)
 
[Support me on Patreon](https://www.patreon.com/cumulus13)