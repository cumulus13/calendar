#!/usr/bin/env python3
#coding:utf-8
"""
  Author:  Hadi Cahyadi --<cumulus13@gmail.com>
  Purpose: Show Calendar in terminal with holidays and day off customize.
           Holiday data is fetched from the Nager.Date public holiday API
           (https://date.nager.at) -- free, no API key, 100+ countries --
           and cached locally. ALL day types (public holiday, bank, school,
           authorities, optional, observance, custom day-off, excluded) can
           be read from and written to the .ini config file.
  Created: 09/11/24
  Updated: 06/29/26
  License: MIT
"""

import calendar
import configparser
import json
import sys
import time
import argparse
from datetime import date, datetime
from pathlib import Path
import shutil
import os

from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich.box import HORIZONTALS
from rich import traceback as rich_traceback
from configset import configset

try:
    import requests
except ImportError:
    requests = None

try:
    from pydebugger.debug import debug
except ImportError:
    def debug(*args, **kwargs):
        return

console = Console()
rich_traceback.install(theme='fruity', max_frames=30, width=shutil.get_terminal_size()[0])

NAGER_API_BASE = "https://date.nager.at/api/v3"
DEFAULT_COUNTRY = "ID"

# Every recognized day "type". `section` is the .ini section it lives in.
# `style` is used to color the day cell in the grid, `list_style` colors
# the legend line below each month, `label` is the human readable name.
# public/bank/school/authorities/optional/observance map 1:1 to the
# `types` field returned by the Nager.Date API. `dayoff` is for
# user/company-specific days off that have nothing to do with the API.
DAY_TYPES = {
    'public':       {'section': 'holidays',     'style': 'cyan on #FF0000',  'list_style': 'bold white on red',      'label': 'Public Holiday'},
    'bank':         {'section': 'bank',         'style': 'black on #FFAA00', 'list_style': 'bold black on #FFAA00',  'label': 'Bank Holiday'},
    'school':       {'section': 'school',       'style': 'black on #00FFAA', 'list_style': 'bold black on #00FFAA',  'label': 'School Holiday'},
    'authorities':  {'section': 'authorities',  'style': 'white on #5555FF', 'list_style': 'bold white on #5555FF',  'label': 'Authorities Holiday'},
    'optional':     {'section': 'optional',     'style': 'black on #AAAAAA', 'list_style': 'bold black on #AAAAAA',  'label': 'Optional Holiday'},
    'observance':   {'section': 'observance',   'style': 'black on #FFFF55', 'list_style': 'bold black on #FFFF55',  'label': 'Observance'},
    'dayoff':       {'section': 'dayoffs',      'style': 'black on #FF55FF', 'list_style': '#ffffff on magenta',     'label': 'Day Off'},
}

# Priority order when a date matches more than one type (first match wins
# for the cell color in the grid; all matches are still listed below).
STYLE_PRIORITY = ['public', 'dayoff', 'bank', 'school', 'authorities', 'optional', 'observance']


class Kalender:
    CONFIGFILE = str(Path(__file__).parent / 'kalender.ini')
    CONFIG = configset(CONFIGFILE)

    days = {t: {} for t in DAY_TYPES}          # {type: {date: name}}
    excluded = set()                            # dates suppressed from API fetch
    country = DEFAULT_COUNTRY
    year = datetime.now().year

    # backward-compat aliases (old code/external scripts may still use these)
    indonesian_holidays = {}
    day_offs = {}

    current_day = datetime.now().date()
    current_datetime = datetime.now()
    cal = calendar.Calendar(firstweekday=0)  # 0 = Monday first

    # ------------------------------------------------------------------ #
    # Raw config helpers (configparser) -- used for ANY read/write that
    # isn't the original holiday/dayoff list parsing, so we never have to
    # guess at configset's write API and never break what already works.
    # ------------------------------------------------------------------ #
    @classmethod
    def _read_raw_config(cls):
        cp = configparser.ConfigParser()
        if Path(cls.CONFIGFILE).exists():
            cp.read(cls.CONFIGFILE, encoding='utf-8')
        return cp

    @classmethod
    def _write_raw_config(cls, cp):
        with open(cls.CONFIGFILE, 'w', encoding='utf-8') as f:
            cp.write(f)
        # refresh configset's view of the file so subsequent reads see the change
        cls.CONFIG = configset(cls.CONFIGFILE)

    @classmethod
    def _get_setting(cls, key, default, section='settings'):
        cp = cls._read_raw_config()
        if cp.has_section(section) and cp.has_option(section, key):
            return cp.get(section, key)
        return default

    @classmethod
    def set_setting(cls, key, value, section='settings'):
        cp = cls._read_raw_config()
        if not cp.has_section(section):
            cp.add_section(section)
        cp.set(section, key, str(value))
        cls._write_raw_config(cp)

    @classmethod
    def _set_raw_entry(cls, section, year, month, day, name):
        key = name.lower().replace(" ", "_").replace("'", "")
        value = f"{year},{month},{day}"
        cp = cls._read_raw_config()
        if not cp.has_section(section):
            cp.add_section(section)
        cp.set(section, key, value)
        cls._write_raw_config(cp)
        return key

    # ------------------------------------------------------------------ #
    # Generic day-type CRUD -- set/get/remove/list ANY day type, backed
    # by the config file. This is the main entry point for "all type of
    # days" management requested.
    # ------------------------------------------------------------------ #
    @classmethod
    def set_day(cls, day_type, year, month, day, name, persist=True, country=None):
        day_type = day_type.lower()
        if day_type not in DAY_TYPES:
            raise ValueError(f"Unknown day type '{day_type}'. Choose from: {', '.join(DAY_TYPES)}")
        base_section = DAY_TYPES[day_type]['section']
        section = f"{base_section}_{country.upper()}" if country else base_section
        key = cls._set_raw_entry(section, year, month, day, name) if persist else name.lower().replace(" ", "_").replace("'", "")
        cls.days.setdefault(day_type, {})[date(year, month, day)] = name
        return key

    @classmethod
    def get_days(cls, day_type=None):
        """Return {date: name} for one type, or {type: {date: name}} for all."""
        if day_type:
            day_type = day_type.lower()
            return dict(cls.days.get(day_type, {}))
        return {t: dict(d) for t, d in cls.days.items()}

    @classmethod
    def remove_day(cls, day_type, date_obj=None, key=None, persist=True, country=None):
        day_type = day_type.lower()
        if day_type not in DAY_TYPES:
            raise ValueError(f"Unknown day type '{day_type}'. Choose from: {', '.join(DAY_TYPES)}")
        base_section = DAY_TYPES[day_type]['section']
        # Try the country-specific section first (if a country was given),
        # then fall back to the global section -- covers entries added
        # either with or without -c.
        sections = [f"{base_section}_{country.upper()}"] if country else []
        sections.append(base_section)
        removed = False

        if persist:
            cp = cls._read_raw_config()
            for section in sections:
                if not cp.has_section(section):
                    continue
                target_key = key
                if target_key is None and date_obj is not None:
                    for k, v in list(cp.items(section)):
                        try:
                            parts = [int(x.strip()) for x in v.split(',')]
                            if date(*parts) == date_obj:
                                target_key = k
                                break
                        except Exception:
                            continue
                if target_key and cp.has_option(section, target_key):
                    cp.remove_option(section, target_key)
                    removed = True
                    cls._write_raw_config(cp)
                    break

        # drop from in-memory cache too
        bucket = cls.days.get(day_type, {})
        if date_obj is not None and date_obj in bucket:
            del bucket[date_obj]
            removed = True
        elif key is not None:
            match = next((d for d, n in bucket.items() if n.lower().replace(' ', '_').replace("'", "") == key), None)
            if match is not None:
                del bucket[match]
                removed = True
        return removed

    @classmethod
    def exclude_date(cls, year, month, day, name='excluded', country=None):
        """Suppress a specific date from being added by the online API fetch."""
        section = f"excluded_{country.upper()}" if country else 'excluded'
        cls._set_raw_entry(section, year, month, day, name)
        cls.excluded.add(date(year, month, day))

    # ------------------------------------------------------------------ #
    # Existing-style date parsing (kept compatible with the original
    # implementation): a config entry looks like  name = year,month,day
    # ------------------------------------------------------------------ #
    @classmethod
    def convert_date(cls, name, section='holidays', default=None):
        debug(section=section)
        debug(name=name)
        data = cls.CONFIG.get_config_as_list(section, name, default)
        if data:
            try:
                cal_name = name.replace("_", " ").split()
                capitalized_words = [word.capitalize() if "'" not in word else word[0].upper() + word[1:] for word in cal_name]
                cal_name = " ".join(capitalized_words)
                debug(cal_name=cal_name)
                return {date(*data): cal_name}
            except Exception as e:
                console.print(f"[bold #FF00FF]Error converting date:[/] [#ffffff on #0000FF]{e}[/]")
                if os.getenv('TRACEBACK') == '1':
                    console.print_exception(theme='fruity', width=shutil.get_terminal_size()[0], max_frames=30)
        return None

    # ------------------------------------------------------------------ #
    # Nager.Date API access, with local on-disk JSON caching
    # ------------------------------------------------------------------ #
    @classmethod
    def _cache_path(cls, year, country):
        return Path(cls.CONFIGFILE).parent / f'.kalender_cache_{country}_{year}.json'

    @classmethod
    def _get_holidays_for_year(cls, year, country):
        if requests is None:
            return []

        cache_days = int(cls._get_setting('cache_days', '30') or 30)
        cache_file = cls._cache_path(year, country)

        if cache_file.exists():
            try:
                age_days = (time.time() - cache_file.stat().st_mtime) / 86400
                if age_days < cache_days:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
            except Exception:
                pass

        try:
            url = f"{NAGER_API_BASE}/PublicHolidays/{year}/{country}"
            resp = requests.get(url, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                try:
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2)
                except Exception:
                    pass
                return data
            else:
                console.print(f"[yellow]Warning: Nager.Date API returned status {resp.status_code} for {country}/{year}[/]")
        except Exception as e:
            console.print(f"[yellow]Warning: could not fetch holidays online ({e}); falling back to cache/config only[/]")
            if cache_file.exists():
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception:
                    pass
        return []

    @classmethod
    def print_available_countries(cls):
        if requests is None:
            console.print("[red]'requests' package required: pip install requests[/]")
            return
        try:
            resp = requests.get(f"{NAGER_API_BASE}/AvailableCountries", timeout=8)
            resp.raise_for_status()
            countries = resp.json()
        except Exception as e:
            console.print(f"[red]Could not fetch country list: {e}[/]")
            return
        table = Table(title="Nager.Date Supported Countries")
        table.add_column("Code", style="bold cyan")
        table.add_column("Name", style="white")
        for c in sorted(countries, key=lambda x: x.get('name', '')):
            table.add_row(c.get('countryCode', ''), c.get('name', ''))
        console.print(table)

    # ------------------------------------------------------------------ #
    # Setup: load config-defined entries for every type, then merge in
    # the online (or cached) API data, unless a date was excluded or
    # already manually defined (manual config entries always win).
    # ------------------------------------------------------------------ #
    @classmethod
    def setup(cls, year=None, country=None, fetch=None):
        cls.year = year or cls.current_day.year
        cls.country = (country or cls._get_setting('country', DEFAULT_COUNTRY)).upper()
        if fetch is None:
            fetch = str(cls._get_setting('auto_fetch', '1')).lower() in ('1', 'true', 'yes', 'on')

        cls.days = {t: {} for t in DAY_TYPES}

        if not cls.CONFIG.has_section('holidays'):
            console.print("[yellow]Note: no 'holidays' section in config yet -- it will be created as needed.[/]")

        # 1. manual / config-defined entries for every known type --
        #    global section first, then this country's own section on top
        #    (country-specific entries override global ones on the same date)
        for day_type, meta in DAY_TYPES.items():
            base_section = meta['section']
            for section in (base_section, f"{base_section}_{cls.country}"):
                if not cls.CONFIG.has_section(section):
                    continue
                for opt_key in cls.CONFIG.options(section):
                    data = cls.convert_date(opt_key, section)
                    if data:
                        cls.days[day_type].update(data)

        # 2. excluded dates (don't let the API re-add these) -- global + country-specific
        cls.excluded = set()
        for section in ('excluded', f"excluded_{cls.country}"):
            if not cls.CONFIG.has_section(section):
                continue
            for opt_key in cls.CONFIG.options(section):
                data = cls.convert_date(opt_key, section)
                if data:
                    cls.excluded.update(data.keys())

        # 3. online (or cached) holiday data from Nager.Date
        if fetch:
            if requests is None:
                console.print("[yellow]Warning: 'requests' not installed, skipping online holiday fetch (pip install requests)[/]")
            else:
                api_data = cls._get_holidays_for_year(cls.year, cls.country)
                for item in api_data or []:
                    try:
                        d = datetime.strptime(item['date'], '%Y-%m-%d').date()
                    except Exception:
                        continue
                    if d in cls.excluded:
                        continue
                    name = item.get('name') or item.get('localName') or 'Holiday'
                    for t in item.get('types') or ['Public']:
                        t_key = t.lower()
                        if t_key not in DAY_TYPES:
                            t_key = 'public'
                        # manual config entries take precedence over the API
                        cls.days[t_key].setdefault(d, name)

        # backward-compat aliases
        cls.indonesian_holidays = cls.days['public']
        cls.day_offs = cls.days['dayoff']

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #
    @classmethod
    def _day_style(cls, day_date):
        for t in STYLE_PRIORITY:
            if day_date in cls.days.get(t, {}):
                return DAY_TYPES[t]['style']
        return None

    @classmethod
    def get_month_calendar_text(cls, year, month):
        month_title = Text(f"{calendar.month_name[month]} {year}\n", style="bold #FF5500 underline")

        month_body = Text()
        month_body.append("Mo Tu We Th Fr Sa Su\n")

        month_days = cls.cal.monthdayscalendar(year, month)

        for week in month_days:
            week_text = Text()
            for idx, day in enumerate(week):
                if day == 0:
                    week_text.append("   ")
                else:
                    day_date = date(year, month, day)
                    if day_date == cls.current_day:
                        week_text.append(f"{day:2} ", style="black on #AAFFFF blink")
                    else:
                        style = cls._day_style(day_date)
                        if style:
                            week_text.append(f"{day:2} ", style=style)
                        elif idx == 6:
                            week_text.append(f"{day:2} ", style="#FF0000")
                        elif idx == 5:
                            week_text.append(f"{day:2} ", style="#FFFF00")
                        else:
                            week_text.append(f"{day:2} ", style="#55FFFF")
            month_body.append(week_text)
            month_body.append("\n")

        full_month_text = Text()
        full_month_text.append(month_title)
        full_month_text.append(month_body)

        full_month_text.append("\nHolidays and Days Off:\n", style="bold underline")
        for t in STYLE_PRIORITY:
            meta = DAY_TYPES[t]
            for d, name in sorted(cls.days.get(t, {}).items()):
                if d.year == year and d.month == month:
                    full_month_text.append(f"• {d.day}: {name} ({meta['label']})\n", style=meta['list_style'])

        return full_month_text

    @classmethod
    def display_current_datetime(cls):
        day_name = cls.current_datetime.strftime("%A")
        date_str = cls.current_datetime.strftime("%d %B %Y")
        time_str = cls.current_datetime.strftime("%H:%M:%S")

        datetime_text = Text()
        datetime_text.append("Current Date & Time: ", style="bold #FF5500")
        datetime_text.append(f"{day_name}, ", style="bold #55FFFF")
        datetime_text.append(f"{date_str} ", style="bold #FFFF00")
        datetime_text.append(f"• {time_str}", style="bold #00FF00")

        panel = Panel(datetime_text, border_style="#FF5500", padding=(0, 2), expand=True)
        console.print(panel)

    @classmethod
    def print_days_table(cls, day_type='all'):
        types_to_show = list(DAY_TYPES.keys()) if day_type == 'all' else [day_type.lower()]
        table = Table(title=f"Configured / Fetched Days — {cls.year} ({cls.country})")
        table.add_column("Date", style="bold yellow")
        table.add_column("Type", style="bold cyan")
        table.add_column("Name", style="white")
        rows = []
        for t in types_to_show:
            for d, name in cls.days.get(t, {}).items():
                rows.append((d, DAY_TYPES[t]['label'], name))
        rows.sort(key=lambda r: r[0])
        for d, label, name in rows:
            table.add_row(d.isoformat(), label, name)
        console.print(table)

    @classmethod
    def display_full_year_in_grid(cls, year, country=None, fetch=None):
        cls.setup(year=year, country=country, fetch=fetch)

        header = Text()
        header.append(f"Year {cls.year} ", style="bold #FFFF00")
        header.append(f"— Country: {cls.country}", style="bold #55FFFF")
        console.print(Panel(header, border_style="#5555FF", expand=True))

        month_blocks = [cls.get_month_calendar_text(year, m) for m in range(1, 13)]

        # IMPORTANT: this is ONE table holding all 12 months (3 rows x 4
        # columns), not three separate layouts. Column widths are computed
        # once across every cell, so every month lines up with every other
        # month no matter how long a holiday/day-off name happens to be in
        # any single month -- long legend text just wraps (folds) inside
        # its own cell instead of widening that row relative to the others.
        cols_per_row = 4
        grid = Table(
            box=HORIZONTALS,
            show_header=False,
            show_edge=False,
            show_lines=True,
            padding=(0, 1),
            expand=True,
            border_style="#555555",
        )
        for _ in range(cols_per_row):
            grid.add_column(ratio=1, overflow="fold")
        for i in range(0, 12, cols_per_row):
            grid.add_row(*month_blocks[i:i + cols_per_row])

        console.print(grid)
        cls.display_current_datetime()


# ---------------------------------------------------------------------- #
# CLI
# ---------------------------------------------------------------------- #
def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Terminal calendar with holidays/day-offs, powered by the free Nager.Date API.",
        epilog=(
            "Examples:\n"
            "  kalender.py                          show current year, default/configured country\n"
            "  kalender.py -y 2026 -c US             show 2026 for the United States\n"
            "  kalender.py --no-fetch                show using config/cache only, no network call\n"
            "  kalender.py --refresh -c DE            force a fresh online fetch for Germany\n"
            "  kalender.py set-country DE             persist DE as the default country\n"
            "  kalender.py add dayoff 2026-09-23 'Company Day Off'\n"
            "  kalender.py add dayoff 2026-09-23 'Company Day Off' -c ID   (only for ID)\n"
            "  kalender.py add bank 2026-12-24 'Christmas Eve' -c US\n"
            "  kalender.py remove dayoff --date 2026-09-23 -c ID\n"
            "  kalender.py exclude 2026-01-06 --name Epiphany -c DE\n"
            "  kalender.py list public\n"
            "  kalender.py countries\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('-y', '--year', type=int, default=None, help="Year to display (default: current year)")
    parser.add_argument('-c', '--country', default=None, help="ISO 3166-1 alpha-2 country code, e.g. ID, US, DE (default: from config, fallback ID)")
    parser.add_argument('--no-fetch', action='store_true', help="Don't fetch holidays online, use config/cache only")
    parser.add_argument('--refresh', action='store_true', help="Ignore the local cache and force a fresh online fetch")

    sub = parser.add_subparsers(dest='command')

    p_add = sub.add_parser('add', help='Add/set a day entry, persisted to the config file')
    p_add.add_argument('type', choices=list(DAY_TYPES.keys()), help='Day type')
    p_add.add_argument('date', help='Date in YYYY-MM-DD format')
    p_add.add_argument('name', help='Name/label for this day')
    p_add.add_argument('-c', '--country', default=argparse.SUPPRESS,
                        help='Scope this entry to one country (ISO alpha-2, e.g. US). Omit to apply to every country.')

    p_rm = sub.add_parser('remove', help='Remove a day entry from the config file')
    p_rm.add_argument('type', choices=list(DAY_TYPES.keys()), help='Day type')
    p_rm.add_argument('--date', help='Date in YYYY-MM-DD format to remove')
    p_rm.add_argument('--key', help='Config key to remove (alternative to --date)')
    p_rm.add_argument('-c', '--country', default=argparse.SUPPRESS,
                       help='Remove the country-scoped entry for this country instead of the global one')

    p_excl = sub.add_parser('exclude', help='Exclude a specific date from online-fetched holidays')
    p_excl.add_argument('date', help='Date in YYYY-MM-DD format to exclude')
    p_excl.add_argument('--name', default='excluded', help='Optional label for the exclusion')
    p_excl.add_argument('-c', '--country', default=argparse.SUPPRESS,
                         help='Scope this exclusion to one country. Omit to exclude for every country.')

    p_list = sub.add_parser('list', help='List configured/fetched days for a year')
    p_list.add_argument('type', nargs='?', choices=list(DAY_TYPES.keys()) + ['all'], default='all')

    sub.add_parser('countries', help='List all country codes supported by Nager.Date')

    p_setc = sub.add_parser('set-country', help='Persist the default country code into the config file')
    p_setc.add_argument('country')

    return parser


def _parse_date_arg(value):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        console.print(f"[red]Invalid date '{value}', expected YYYY-MM-DD[/]")
        sys.exit(1)


def main():
    parser = build_arg_parser()
    args = parser.parse_args()
    year = args.year or Kalender.current_day.year
    country = args.country

    if args.command == 'add':
        d = _parse_date_arg(args.date)
        key = Kalender.set_day(args.type, d.year, d.month, d.day, args.name, country=country)
        scope = f"country={country}" if country else "all countries"
        console.print(f"[green]Added {args.type} '{args.name}' on {d.isoformat()} ({scope}, key={key})[/]")
        return

    if args.command == 'remove':
        d = _parse_date_arg(args.date) if args.date else None
        if not d and not args.key:
            console.print("[red]Provide --date or --key[/]")
            sys.exit(1)
        Kalender.setup(year=year, country=country, fetch=False)
        ok = Kalender.remove_day(args.type, date_obj=d, key=args.key, country=country)
        scope = f"country={country}" if country else "global"
        if ok:
            console.print(f"[green]Removed {args.type} entry ({args.date or args.key}, {scope})[/]")
        else:
            console.print(f"[yellow]No {args.type} entry found ({args.date or args.key}, {scope})[/]")
        return

    if args.command == 'exclude':
        d = _parse_date_arg(args.date)
        Kalender.exclude_date(d.year, d.month, d.day, args.name, country=country)
        scope = f"for {country}" if country else "for every country"
        console.print(f"[green]Excluded {d.isoformat()} {scope} from future online holiday fetches[/]")
        return

    if args.command == 'set-country':
        Kalender.set_setting('country', args.country.upper())
        console.print(f"[green]Default country set to {args.country.upper()}[/]")
        return

    if args.command == 'countries':
        Kalender.print_available_countries()
        return

    if args.command == 'list':
        Kalender.setup(year=year, country=country, fetch=not args.no_fetch)
        Kalender.print_days_table(args.type)
        return

    # default: show the full-year grid
    if args.refresh:
        c = (country or Kalender._get_setting('country', DEFAULT_COUNTRY)).upper()
        cache_file = Kalender._cache_path(year, c)
        if cache_file.exists():
            cache_file.unlink()

    Kalender.display_full_year_in_grid(year, country=country, fetch=not args.no_fetch)


if __name__ == '__main__':
    main()
