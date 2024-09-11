#!/usr/bin/env python3
#coding:utf-8
"""
  Author:  Hadi Cahyadi --<cumulus13@gmail.com>
  Purpose: Show Calendar in terminal with holidays and day off customize
  Created: 09/11/24
  License: MIT
"""

import calendar
from datetime import date, datetime
from rich.console import Console
from rich.text import Text
from rich.columns import Columns
from rich import traceback as rich_traceback
from configset import configset
from pathlib import Path
import shutil
import os, sys
try:
    from pydebugger.debug import debug
except:
    def debug(*args, **kwargs):
        return 

# Initialize the rich console
console = Console()
rich_traceback.install(theme='fruity', max_frames=30, width=shutil.get_terminal_size()[0])

class Kalender:
    CONFIGFILE = str(Path(__file__).parent / 'kalender.ini')
    CONFIG = configset(CONFIGFILE)
    indonesian_holidays = {}
    day_offs = {}
    # Get the current date for highlighting the current day
    current_day = datetime.now().date()
    # Create a calendar instance
    cal = calendar.Calendar(firstweekday=0)  # 0 means Sunday is the first day of the week        

    @classmethod
    def convert_date(self, name, section='holidays', default=None):
        # This method converts date from the config file
        debug(section = section)
        debug(name = name)
        data = self.CONFIG.get_config_as_list(section, name, default)
        if data:
            try:
                cal_name = name.replace("_", " ").split()
                # Capitalize each word, except for the part after the apostrophe
                capitalized_words = [word.capitalize() if "'" not in word else word[0].upper() + word[1:] for word in cal_name]
                
                # Join the capitalized words back into a string
                cal_name = " ".join(capitalized_words)
                debug(cal_name = cal_name)
                
                return {date(*data): cal_name}
            except Exception as e:
                console.print(f"[bold #FF00FF]Error converting date:[/] [#ffffff in #0000FF]{e}[/]")
                if os.getenv('TRACEBACK') == '1':
                    console.print_exception(theme='fruity', width=shutil.get_terminal_size()[0], max_frames=30)
        return None

    @classmethod
    def setup(self):
        # Debugging to see if config file is loaded
        #console.print(f"CONFIGFILE: {self.CONFIGFILE}")

        # Check if the section 'holidays' exists in the config
        if not self.CONFIG.has_section('holidays'):
            console.print("[bold red]Error: No 'holidays' section found in config file.[/]")
            return

        # Loop through holidays in the 'holidays' section
        for holiday in self.CONFIG.options('holidays'):
            debug(holiday=holiday)
            data = self.convert_date(holiday)
            debug(data_holiday=data)
            
            if data: self.indonesian_holidays.update(data)
        
        #print('-' *shutil.get_terminal_size()[0])
        
        for dayoff in self.CONFIG.options('dayoffs'):
            debug(dayoff=dayoff)
            data = self.convert_date(dayoff, 'dayoffs')
            debug(data_dayoff=data)
            
            if data: self.day_offs.update(data)
        
        ## Adding default holidays if necessary
        #self.indonesian_holidays = {
            #date(2024, 1, 1): "New Year's Day",
            #date(2024, 3, 11): "Nyepi",
            #date(2024, 4, 10): "Good Friday",
            #date(2024, 4, 22): "Eid al-Fitr",
            #date(2024, 5, 1): "Labour Day",
            #date(2024, 5, 23): "Ascension Day",
            #date(2024, 6, 1): "Pancasila Day",
            #date(2024, 6, 17): "Idul Adha",
            #date(2024, 8, 17): "Independence Day",
            #date(2024, 12, 25): "Christmas Day"
        #}
        
        # Define day offs (you can add company-specific day offs if needed)
        #self.day_offs = {
            #date(2024, 9, 23): "Company Day Off",
        #}
    
    # Create a function to generate the calendar for a single month
    @classmethod
    def get_month_calendar_text(self, year, month):
        # Create a separate Text object for the month title (only the title is underlined)
        month_title = Text(f"{calendar.month_name[month]} {year}\n", style="bold #FF5500 underline")
        
        # Create a Text object for the month body (days and weekdays, no underline)
        month_body = Text()
        month_body.append("Mo Tu We Th Fr Sa Su\n")
    
        # Generate the month's days
        month_days = self.cal.monthdayscalendar(year, month)
    
        # Print the calendar days, marking holidays, days off, and the current day
        for week in month_days:
            week_text = Text()  # Initialize an empty Text object for the week
            for idx, day in enumerate(week):
                if day == 0:
                    # Empty day (previous/next month overflow)
                    week_text.append("   ")  # Add empty space
                else:
                    day_date = date(year, month, day)
                    if day_date == self.current_day:
                        # Current day - black text with cyan background
                        week_text.append(f"{day:2} ", style="black on #AAFFFF blink")
                    elif day_date in self.indonesian_holidays:
                        # Holiday - white text with red background
                        week_text.append(f"{day:2} ", style="cyan on #FF0000")
                    elif day_date in self.day_offs:
                        # Day off - black text with magenta background
                        week_text.append(f"{day:2} ", style="black on #FF55FF")
                    elif idx == 6:
                        # Sunday - red text
                        week_text.append(f"{day:2} ", style="#FF0000")
                    elif idx == 5:
                        # Saturday - yellow text
                        week_text.append(f"{day:2} ", style="#FFFF00")
                    else:
                        # Weekday (Monday to Friday) - cyan text
                        week_text.append(f"{day:2} ", style="#55FFFF")
            month_body.append(week_text)
            month_body.append("\n")
        
        # Combine the title and the body
        full_month_text = Text()
        full_month_text.append(month_title)
        full_month_text.append(month_body)
    
        # Add holidays and day offs for this month
        full_month_text.append("\nHolidays and Days Off:\n", style="bold underline")
        
        # List holidays for the month
        for holiday_date, holiday_name in self.indonesian_holidays.items():
            if holiday_date.year == year and holiday_date.month == month:
                full_month_text.append(f"• {holiday_date.day}: {holiday_name}\n", style="bold white on red")
    
        # List day offs for the month
        for day_off_date, day_off_name in self.day_offs.items():
            if day_off_date.year == year and day_off_date.month == month:
                full_month_text.append(f"• {day_off_date.day}: {day_off_name}\n", style="#ffffff on magenta")
        
        return full_month_text
    
    # Create a function to display the calendar in a grid format
    @classmethod
    def display_full_year_in_grid(self, year):
        self.setup()
        # Store the month text blocks
        month_blocks = []
    
        for month in range(1, 13):
            # Generate each month's calendar and add it to the list
            month_blocks.append(self.get_month_calendar_text(year, month))
    
        # Print the entire calendar in grid format (3 months per row)
        for i in range(0, 12, 4):  # Step through months 3 at a time
            row = Columns(month_blocks[i:i+4], expand=True)
            console.print(row)

if __name__ == '__main__':
    # Call Class function to display the full-year calendar in grid format
    Kalender.display_full_year_in_grid(2024)

