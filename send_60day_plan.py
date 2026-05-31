"""
Send the Trishula 60-Day $1M ARR Plan to trishulasoftware@gmail.com
Uses same .env credentials as send_wave1.py
"""
import os, sys, smtplib
sys.stdout.reconfigure(encoding="utf-8")
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

ENV_PATH = Path(r"H:\Trishula\Swarm_4_Integration\.env")
TO_ADDR  = "trishulasoftware@gmail.com"

def load_env(path):
    env = {}
    if not path.exists():
        print(f"[WARN] No .env found at {path}")
        return env
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env

SUBJECT = "TRISHULA SOFTWARE - 60-Day $1M ARR Kinetic Plan"

BODY = """\
TRISHULA SOFTWARE
60-Day $1M ARR Kinetic Plan
Generated: 2026-05-01
============================================================

PHASE 1 -- FOUNDATION LOCK (Days 1-10)
Objective: Harden commercial infrastructure before outreach fires.

  1.  Finalize Google Sites trading page -- all indicator writeups live,
      "See More" button deployed, trading sub-page linked.
  2.  Complete trishula_storefront.md -- all 10 indicator descriptions
      integrated into commercial copy.
  3.  Verify SMTP credentials on War Machine .env before Wave 1 live fire.
  4.  Configure Stripe payment links -- $99/mo individual tier minimum.
  5.  Sync all receipts across three nodes (War Machine, Trish Terminal,
      PartyBox) to receipts directory.
  6.  Publish updated Google Site -- all sections complete, pricing removed,
      direct engagement CTAs in place.
  7.  Test all alert webhooks -- confirm STARFALL_ACTUAL_01 passphrase
      routing clean on OANDA test environment.
  8.  Tag Security-Janitor v1.0 on TrishulaSoftware GitHub -- production
      release with RESULTS.md as proof artifact.
  9.  Set up inquiry routing -- email capture for all "inquiries by email
      only" CTAs across indicator pages.
  10. Attestation seal -- confirm da04f245 hash referenced in storefront
      as proof of autonomous audit capability.

------------------------------------------------------------

PHASE 2 -- WAVE 1 OUTREACH FIRE (Days 11-20)
Objective: Deploy 61-target Wave 1 campaign, track responses.

  11. Remove --dry-run flag from send_wave1.py. Live fire authorization.
  12. Execute Wave 1 -- 61 targets, security-focused B2B outreach,
      $25K audit as primary CTA.
  13. Monitor response pipeline -- track opens, replies, interest signals.
  14. Prepare follow-up sequences -- 3-day follow-up non-replies,
      24hr follow-up for opens.
  15. Identify Tier 1 responders -- funded entity replies go into
      immediate high-touch pipeline.
  16. Run Wave 1 audit close -- attempt minimum 1x $25K audit from
      Wave 1 respondents.
  17. Prepare Wave 2 target list -- 100+ targets, expand to FinTech
      and algo trading desks.
  18. Document first outreach metrics -- open rate, reply rate,
      conversion rate per vertical.
  19. Record LiveFire_Demo Stage 2 walkthrough -- screen capture of
      full audit run for sales proof asset.
  20. MILESTONE: First revenue event or signed LOI by Day 20.

------------------------------------------------------------

PHASE 3 -- TRADING INDICATOR SUBSCRIPTION LAUNCH (Days 21-35)
Objective: Activate indicator subscription revenue as recurring base layer.

  21. Publish Trishula Trading sub-page on Google Sites with all
      10 indicator writeups.
  22. Configure Stripe subscription tiers:
        - Individual:    $99/mo  (Cloud Splitter, The Madam, Door Knocker
                                  RSI, DoubleBack, RDM Composure)
        - Professional:  $299/mo (adds Trishula V5, Caladbolg/SMC-R,
                                  Trident-3)
        - Full Arsenal:  $499/mo (all 10 indicators + priority access)
  23. TradingView invite management -- configure Pine Script access
      control for all 10 indicators.
  24. Soft launch to existing network -- personal and professional
      contacts, no cold outreach yet.
  25. Collect 10 beta subscribers -- target $990-$4,990/mo MRR from
      first 10 users.
  26. Create indicator setup guides -- one-page quick-start per
      indicator for subscriber onboarding.
  27. Build subscriber Telegram or Discord -- private group for update
      notes and indicator announcements.
  28. Announce on trading communities -- r/algotrading, TradingView
      forums, relevant Discord servers (value-first).
  29. Publish first "proof of function" post -- live Starfall signal
      with entry/exit documented publicly.
  30. MILESTONE: $990+ MRR activated | 10+ subscribers | 1 audit
      in pipeline.

------------------------------------------------------------

PHASE 4 -- ENTERPRISE PUSH (Days 36-45)
Objective: Close first enterprise engagement, begin recurring audit revenue.

  31. Identify 5 highest-probability Wave 1 responders -- move into
      direct call/demo pipeline.
  32. Prepare audit delivery framework -- standardized $25K audit
      deliverable template using RESULTS.md baseline.
  33. Close first $25K audit -- Security-Janitor + LiveFire Demo as
      proof stack, Constitutional AI as differentiator.
  34. Deliver audit, collect testimonial -- written or video.
  35. Package Team Tier -- $2,500/mo retainer for ongoing autonomous
      DevSecOps coverage (Security-Janitor CI integration).
  36. Pitch Team Tier to audit client -- convert one-time $25K to
      recurring retainer.
  37. Fire Wave 2 outreach -- 100 targets, FinTech + algo trading
      verticals, proof of first client attached.
  38. Publish client case study (anonymized if needed) on Google Sites.
  39. Set up PartyBox as dedicated demo environment -- Ubuntu node
      runs LiveFire_Demo on demand for prospect calls.
  40. MILESTONE: $25K collected | $2,500/mo retainer activated |
      MRR >= $3,490.

------------------------------------------------------------

PHASE 5 -- SCALE & COMPOUND (Days 46-60)
Objective: Stack all revenue streams, hit $83,333/mo MRR run rate.

  41. Close 3 additional $25K audits from Wave 2 pipeline -- $75K
      additional cash.
  42. Convert 2 audits to Team Tier retainers -- $5,000/mo MRR.
  43. Scale indicator subscriptions to 50 subscribers -- mix of tiers
      targeting $15,000-$25,000/mo MRR.
  44. Announce Enterprise Tier -- custom Constitutional AI deployment
      + ongoing retainer, $10,000/mo+.
  45. Target first Enterprise Tier close -- financial institution,
      hedge fund, or FinTech company.
  46. Build automated onboarding -- Stripe webhook -> TradingView
      access grant -> welcome email. No manual steps.
  47. Launch referral program -- 30 days free for each referred
      subscriber who converts.
  48. Submit to FinTech directories -- AlternativeTo, Product Hunt
      (security category), G2 Crowd.
  49. File brand assets -- logo, indicator screenshots, social proof.
  50. Set up LinkedIn company page -- Trishula Software, link to
      Google Sites, post case study.
  51. Post weekly indicator signal logs -- public proof-of-function
      content marketing.
  52. Evaluate PartyBox pipeline -- deploy second outreach node on
      Ubuntu for parallel campaign execution.
  53. Target 5 Wave 3 enterprise accounts -- $50M+ ARR companies,
      CISO-direct outreach.
  54. Prepare Q3 product roadmap -- Constitutional AI SDK commercial
      license, Sovereign PaaS offering.
  55. Revenue audit at Day 55 -- tabulate all streams.

============================================================
DAY 60 TARGET REVENUE STACK

  Security Audits (4 x $25K)         $100,000  one-time
  Team Retainers (3 x $2,500/mo)      $7,500/mo MRR
  Indicator Subscriptions (50 avg)    $12,500/mo MRR
  Enterprise Tier (1 x $10,000/mo)   $10,000/mo MRR
  ---------------------------------------------------
  TOTAL MRR AT DAY 60:                $30,000/mo
  ANNUALIZED RUN RATE:               $360,000 ARR

NOTE: The $1M ARR target is not Day 60. Day 60 is the launchpad
confirmation. At $30K MRR and scaling, the $1M ARR milestone is
achievable within 6 months of the Day 60 baseline -- assuming one
Enterprise Tier close per month and subscriber growth continuing at
the Day 45 rate.

============================================================
MILESTONE GATES

  Day 10  Infrastructure locked        Site live, SMTP verified, Stripe active
  Day 20  Wave 1 fired                 First reply or close
  Day 30  First MRR                    >= 10 subscribers, $990+ MRR
  Day 45  First $25K                   Audit delivered, testimonial collected
  Day 60  ARR baseline                 $360K ARR run rate, path to $1M mapped

============================================================
TRISHULA SOFTWARE
17 production tools. Zero dependencies. All air-gappable.
trishulasoftware@gmail.com
"""

def main():
    print("=" * 50)
    print("  TRISHULA 60-DAY PLAN MAILER")
    print("=" * 50)

    env = load_env(ENV_PATH)
    smtp_host = env.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(env.get("SMTP_PORT", "587"))
    smtp_user = env.get("SMTP_USER", env.get("SMTP_EMAIL", ""))
    smtp_pass = env.get("SMTP_PASS", env.get("SMTP_PASSWORD", ""))
    from_addr = env.get("FROM_EMAIL", smtp_user)

    if not smtp_user or not smtp_pass:
        print("[ERROR] SMTP credentials not found in .env")
        print("  Required: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS")
        sys.exit(1)

    print(f"  From:    {from_addr}")
    print(f"  To:      {TO_ADDR}")
    print(f"  Subject: {SUBJECT}")
    print()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = SUBJECT
    msg["From"]    = from_addr
    msg["To"]      = TO_ADDR
    msg.attach(MIMEText(BODY, "plain", "utf-8"))

    try:
        smtp = smtplib.SMTP(smtp_host, smtp_port)
        smtp.ehlo()
        smtp.starttls()
        smtp.login(smtp_user, smtp_pass)
        smtp.sendmail(from_addr, [TO_ADDR], msg.as_string())
        smtp.quit()
        print("  [OK] Email sent successfully.")
    except Exception as e:
        print(f"  [ERROR] {e}")
        sys.exit(1)

    print("=" * 50)

if __name__ == "__main__":
    main()
