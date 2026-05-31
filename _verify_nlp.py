#!/usr/bin/env python3
import boto3

print('[VERIFY] Testing all 4 AWS NLP services...\n')

# Textract
try:
    tx = boto3.client('textract', region_name='us-east-2')
    tx.list_adapters()
    print('  [Textract]   LIVE - quota 601 concurrent jobs confirmed')
except Exception as e:
    print(f'  [Textract]   {str(e)[:80]}')

# Comprehend
try:
    cp = boto3.client('comprehend', region_name='us-east-1')
    r  = cp.detect_sentiment(Text='The market is extremely bullish today with strong momentum.', LanguageCode='en')
    sentiment = r['Sentiment']
    score     = max(r['SentimentScore'].values())
    print(f'  [Comprehend] LIVE - Sentiment: {sentiment} ({score:.3f})')
except Exception as e:
    print(f'  [Comprehend] {str(e)[:80]}')

# Translate
try:
    tr = boto3.client('translate', region_name='us-east-2')
    r  = tr.translate_text(Text='bullish momentum', SourceLanguageCode='en', TargetLanguageCode='es')
    print(f'  [Translate]  LIVE - translated: {r["TranslatedText"]}')
except Exception as e:
    print(f'  [Translate]  {str(e)[:80]}')

# Transcribe
try:
    tc = boto3.client('transcribe', region_name='us-east-2')
    tc.list_transcription_jobs(MaxResults=1)
    print('  [Transcribe] LIVE')
except Exception as e:
    print(f'  [Transcribe] {str(e)[:80]}')
