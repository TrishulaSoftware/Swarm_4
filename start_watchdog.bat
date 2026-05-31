@echo off
:: Trishula Sovereign Watchdog — runs at Windows startup (no admin needed)
:: Drop this .bat in: shell:startup  (Win+R → shell:startup)
cd /d "H:\Trishula\Swarm_4_Integration\Salvo_Staging"
start "Trishula Watchdog" /min "C:\Users\War Machine\AppData\Local\Python\pythoncore-3.14-64\python.exe" "H:\Trishula\Swarm_4_Integration\Salvo_Staging\sovereign_watchdog.py"
