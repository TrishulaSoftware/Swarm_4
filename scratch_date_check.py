import yfinance as yf, warnings, pandas as pd
warnings.filterwarnings('ignore')
hist = yf.Ticker('AMZN').history(period='30d', interval='1d', auto_adjust=True)
hist.index = hist.index.tz_localize(None) if hist.index.tz else hist.index
print('AMZN dates available:')
for d, row in hist.iterrows():
    print(f"  {str(d)[:10]}  close={row['Close']:.2f}")
