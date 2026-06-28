@echo off
REM ============================================================
REM Taynton Bay Capital - Macro Compass daily data refresh
REM Registered as Windows Task "MacroCompass-Daily" (weekdays 5:30 PM ET)
REM ============================================================
cd /d C:\Users\zachc\Desktop\macro_sentiment
set PYTHONPATH=C:\Users\zachc\Desktop\macro_sentiment

echo ======================================== >> output\scheduler.log
echo MacroCompass Daily Refresh - %date% %time% >> output\scheduler.log

"C:\Users\zachc\Desktop\ca_equity_fund\.venv\Scripts\python.exe" run_macro.py --full >> output\scheduler.log 2>&1

echo Completed at %date% %time% >> output\scheduler.log
echo ======================================== >> output\scheduler.log
