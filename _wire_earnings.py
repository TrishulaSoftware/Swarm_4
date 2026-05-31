path = r'H:\Trishula\Swarm_4_Integration\Salvo_Staging\_run_full_stack.py'
src = open(path, encoding='utf-8').read()

if 'qmatrix_earnings' not in src:
    src = src.replace(
        'from qmatrix_altmarkets import run_altmarkets_sweep',
        'from qmatrix_altmarkets import run_altmarkets_sweep\nfrom qmatrix_earnings import run_earnings_sweep'
    )

DONE_LINE = 'print("[DONE] Full sweep complete.")'
EARNINGS_CALL = 'run_earnings_sweep(s.WEBHOOK_EARNINGS)\n' + DONE_LINE
if 'run_earnings_sweep' not in src:
    src = src.replace(DONE_LINE, EARNINGS_CALL)

open(path, 'w', encoding='utf-8').write(src)
print('Full stack updated with earnings sweep.')
