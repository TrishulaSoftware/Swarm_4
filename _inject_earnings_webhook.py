path = r'H:\Trishula\Swarm_4_Integration\Salvo_Staging\sovereign_options_scanner.py'
src  = open(path, encoding='utf-8').read()

EARNINGS_LINE = '\nWEBHOOK_EARNINGS   = "https://discord.com/api/webhooks/1508522150657654935/bh9OgEkGq-rgDbZ80e89Fkq4ATFWbPB5dwqODF2U0P-91IyYY-YKf6djYqL-7giEIG4F"'
ANCHOR = 'WEBHOOK_LOWCAP     = "https://discord.com/api/webhooks/1508274874697781429/3Nl6GKPMazt1RUFOO3WLXXSrc2gPf6KaIddOWkQc6bHYv0ryJrEqeh1ZraO35mFVkyIx"'

if 'WEBHOOK_EARNINGS' in src:
    print('Already present.')
else:
    new_src = src.replace(ANCHOR, ANCHOR + EARNINGS_LINE, 1)
    open(path, 'w', encoding='utf-8').write(new_src)
    print('WEBHOOK_EARNINGS injected.')
