#!/usr/bin/env python3
"""AWS NLP Service Activation Test — fires all 6 services."""
import boto3, json
from datetime import datetime, timezone

REGION = 'us-east-2'
NOW = datetime.now(timezone.utc).isoformat()
results = {}

print()
print("=" * 58)
print("  AWS NLP SERVICES — ACTIVATION TEST")
print(f"  Region: {REGION} | Time: {NOW[:19]}")
print("=" * 58)

# 1. Comprehend
for region in ['us-east-2', 'us-east-1', 'us-west-2']:
    try:
        c = boto3.client('comprehend', region_name=region)
        r = c.detect_sentiment(Text='Jayson Tatum is doubtful tonight', LanguageCode='en')
        print(f"  [COMPREHEND] LIVE ({region}) - Sentiment: {r['Sentiment']}")
        scores = r['SentimentScore']
        print(f"               Neg:{scores['Negative']:.2f} Pos:{scores['Positive']:.2f}")
        results['comprehend'] = {'status': 'LIVE', 'region': region}
        break
    except Exception as e:
        err = str(e)[:80]
        print(f"  [COMPREHEND] {region}: {err}")
        results['comprehend'] = {'status': 'ERROR', 'error': err}

# 2. Translate
try:
    t = boto3.client('translate', region_name=REGION)
    r = t.translate_text(Text='options scanner active', SourceLanguageCode='en', TargetLanguageCode='es')
    print(f"  [TRANSLATE]  LIVE - '{r['TranslatedText']}'")
    results['translate'] = {'status': 'LIVE'}
except Exception as e:
    print(f"  [TRANSLATE]  {str(e)[:80]}")
    results['translate'] = {'status': 'ERROR', 'error': str(e)[:80]}

# 3. Polly
try:
    p = boto3.client('polly', region_name=REGION)
    r = p.describe_voices(LanguageCode='en-US')
    count = len(r['Voices'])
    print(f"  [POLLY]      LIVE - {count} voices available")
    results['polly'] = {'status': 'LIVE', 'voices': count}
except Exception as e:
    print(f"  [POLLY]      {str(e)[:80]}")
    results['polly'] = {'status': 'ERROR', 'error': str(e)[:80]}

# 4. Transcribe
try:
    tr = boto3.client('transcribe', region_name=REGION)
    r = tr.list_transcription_jobs(MaxResults=1)
    print(f"  [TRANSCRIBE] LIVE - API accessible")
    results['transcribe'] = {'status': 'LIVE'}
except Exception as e:
    print(f"  [TRANSCRIBE] {str(e)[:80]}")
    results['transcribe'] = {'status': 'ERROR', 'error': str(e)[:80]}

# 5. Textract
try:
    tx = boto3.client('textract', region_name=REGION)
    r = tx.get_document_analysis(JobId='test-nonexistent-id-probe')
except tx.exceptions.InvalidJobIdException:
    print(f"  [TEXTRACT]   LIVE - API accessible (expected probe error)")
    results['textract'] = {'status': 'LIVE'}
except Exception as e:
    err = str(e)[:80]
    if 'InvalidJobIdException' in err or 'InvalidJobId' in err or 'not found' in err.lower():
        print(f"  [TEXTRACT]   LIVE - API accessible")
        results['textract'] = {'status': 'LIVE'}
    else:
        print(f"  [TEXTRACT]   {err}")
        results['textract'] = {'status': 'ERROR', 'error': err}

# 6. Forecast
try:
    fc = boto3.client('forecast', region_name=REGION)
    r = fc.list_datasets()
    print(f"  [FORECAST]   LIVE - {len(r.get('Datasets', []))} datasets")
    results['forecast'] = {'status': 'LIVE', 'activated': NOW}
except Exception as e:
    err = str(e)[:80]
    print(f"  [FORECAST]   {err}")
    results['forecast'] = {'status': 'ERROR', 'error': err}

# 7. Lex (us-east-1 only)
try:
    lx = boto3.client('lex-models', region_name='us-east-1')
    r = lx.get_bots(maxResults=5)
    print(f"  [LEX]        LIVE - {len(r.get('bots', []))} bots (us-east-1)")
    results['lex'] = {'status': 'LIVE'}
except Exception as e:
    print(f"  [LEX]        {str(e)[:80]}")
    results['lex'] = {'status': 'ERROR', 'error': str(e)[:80]}

print("=" * 58)
live = [k for k, v in results.items() if v['status'] == 'LIVE']
errors = [k for k, v in results.items() if v['status'] == 'ERROR']
print(f"  LIVE:   {len(live)}/7  {live}")
print(f"  ERRORS: {len(errors)}/7  {errors}")
print("=" * 58)

# Save results
with open('aws_nlp_activation.json', 'w') as f:
    json.dump({'timestamp': NOW, 'region': REGION, 'results': results}, f, indent=2)
print("  Saved: aws_nlp_activation.json")
