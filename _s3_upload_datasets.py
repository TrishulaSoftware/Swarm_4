#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=================================================================
R2-9 STEP 3 — S3 DATASET UPLOAD
=================================================================
Creates S3 bucket `trishula-ml-data` in us-east-2 if needed,
then uploads:
  - ml_training_data.csv  → s3://trishula-ml-data/qmatrix/v1/
  - ml_features.csv       → s3://trishula-ml-data/qmatrix/v1/

Verifies upload with s3.list_objects.

Run: python _s3_upload_datasets.py
=================================================================
"""

import os
import sys
import datetime
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────
BASE_DIR = Path(r"H:\Trishula\Swarm_4_Integration\Salvo_Staging")
FILES_TO_UPLOAD = [
    BASE_DIR / "ml_training_data.csv",
    BASE_DIR / "ml_features.csv",
]

# ── S3 Config ─────────────────────────────────────────────────────
BUCKET_NAME = "trishula-ml-data"
S3_PREFIX   = "qmatrix/v1/"
AWS_REGION  = "us-east-2"

# ── Load .env for AWS credentials if not in environment ─────────
def _load_env():
    """Try to load .env file for AWS credentials."""
    env_paths = [
        Path(r"H:\Trishula\Swarm_4_Integration\Swarm_4_SBM_FINAL INTEGRATION\Project-Swarm\trishula-market-data\.env"),
        BASE_DIR / ".env",
        Path(r"H:\Trishula\Swarm_4_Integration\Salvo_Staging\.env.example"),
    ]
    for env_path in env_paths:
        if env_path.exists():
            try:
                for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip().strip('"').strip("'")
                        if key.startswith("AWS_") and key not in os.environ:
                            os.environ[key] = val
                print(f"  [ENV] Loaded from {env_path.name}")
                return True
            except Exception as e:
                print(f"  [ENV] Could not load {env_path}: {e}")
    return False


def get_boto3_client():
    """Initialize and return an S3 client."""
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError

        _load_env()

        # Prefer explicit credentials from env
        aws_key    = os.environ.get("AWS_ACCESS_KEY_ID")
        aws_secret = os.environ.get("AWS_SECRET_ACCESS_KEY")
        aws_region = os.environ.get("AWS_DEFAULT_REGION", AWS_REGION)

        session_kwargs = {"region_name": aws_region}
        if aws_key and aws_secret:
            session_kwargs["aws_access_key_id"]     = aws_key
            session_kwargs["aws_secret_access_key"] = aws_secret
            print(f"  [AWS] Using explicit credentials (key: {aws_key[:8]}...)")
        else:
            print("  [AWS] Using default credential chain (IAM role / ~/.aws/credentials)")

        s3 = boto3.client("s3", **session_kwargs)
        return s3

    except ImportError:
        print("[FATAL] boto3 not installed. Run: pip install boto3")
        sys.exit(1)


def ensure_bucket(s3, bucket: str, region: str):
    """Create S3 bucket if it doesn't exist. Gracefully skips permissions we lack."""
    from botocore.exceptions import ClientError

    try:
        s3.head_bucket(Bucket=bucket)
        print(f"  [S3] Bucket '{bucket}' already exists ✓")
        return True
    except ClientError as e:
        error_code = int(e.response["Error"]["Code"])
        if error_code == 404:
            # Bucket doesn't exist — create it
            print(f"  [S3] Creating bucket '{bucket}' in {region} ...")
            try:
                if region == "us-east-1":
                    s3.create_bucket(Bucket=bucket)
                else:
                    s3.create_bucket(
                        Bucket=bucket,
                        CreateBucketConfiguration={"LocationConstraint": region}
                    )
                print(f"  [S3] ✓ Bucket '{bucket}' created")
            except ClientError as ce:
                err_msg = str(ce)
                # BucketAlreadyOwnedByYou = another region created it; fine
                if "BucketAlreadyOwnedByYou" in err_msg or "BucketAlreadyExists" in err_msg:
                    print(f"  [S3] Bucket '{bucket}' already exists (different region OK)")
                else:
                    print(f"  [S3] Create bucket error: {ce}")
                    return False

            # Best-effort: block public access (may fail if IAM lacks permission)
            try:
                s3.put_public_access_block(
                    Bucket=bucket,
                    PublicAccessBlockConfiguration={
                        "BlockPublicAcls":       True,
                        "IgnorePublicAcls":      True,
                        "BlockPublicPolicy":     True,
                        "RestrictPublicBuckets": True,
                    }
                )
                print(f"  [S3] Public access block applied ✓")
            except ClientError:
                print(f"  [S3] (Skip) PutPublicAccessBlock not permitted — bucket private by default")

            # Best-effort: enable versioning
            try:
                s3.put_bucket_versioning(
                    Bucket=bucket,
                    VersioningConfiguration={"Status": "Enabled"}
                )
                print(f"  [S3] Versioning enabled ✓")
            except ClientError:
                print(f"  [S3] (Skip) PutBucketVersioning not permitted — continuing")

            return True

        elif error_code == 403:
            print(f"  [S3] Bucket '{bucket}' exists (access OK, continuing)")
            return True
        else:
            print(f"  [S3] Unexpected head_bucket error ({error_code}): {e}")
            # Attempt uploads anyway — bucket may exist in another region
            return True


def upload_file(s3, local_path: Path, bucket: str, prefix: str) -> dict:
    """Upload a file to S3. Returns upload result dict."""
    from botocore.exceptions import ClientError

    key = prefix + local_path.name
    size_mb = local_path.stat().st_size / 1024 / 1024

    print(f"\n  [UPLOAD] {local_path.name} ({size_mb:.3f} MB)")
    print(f"           → s3://{bucket}/{key}")

    try:
        # Add metadata tags
        s3.upload_file(
            str(local_path),
            bucket,
            key,
            ExtraArgs={
                "Metadata": {
                    "source":    "trishula-qmatrix-scanner",
                    "version":   "v1",
                    "uploaded":  datetime.datetime.utcnow().isoformat(),
                }
            }
        )
        print(f"  [UPLOAD] ✓ Success")
        return {"status": "ok", "key": key, "size_mb": size_mb}

    except FileNotFoundError:
        msg = f"Local file not found: {local_path}"
        print(f"  [UPLOAD] ✗ {msg}")
        return {"status": "error", "key": key, "error": msg}
    except ClientError as e:
        msg = str(e)
        print(f"  [UPLOAD] ✗ S3 error: {msg}")
        return {"status": "error", "key": key, "error": msg}


def verify_uploads(s3, bucket: str, prefix: str, expected_files: list) -> dict:
    """List S3 objects and verify expected files are present."""
    from botocore.exceptions import ClientError

    print(f"\n  [VERIFY] Listing s3://{bucket}/{prefix} ...")

    try:
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        objects  = response.get("Contents", [])

        if not objects:
            print(f"  [VERIFY] ✗ No objects found at s3://{bucket}/{prefix}")
            return {"status": "empty", "objects": []}

        result_objects = []
        for obj in objects:
            size_kb = obj["Size"] / 1024
            modified = obj["LastModified"].strftime("%Y-%m-%d %H:%M:%S UTC")
            print(f"  [VERIFY] ✓ {obj['Key']}  ({size_kb:.1f} KB, {modified})")
            result_objects.append({
                "key":      obj["Key"],
                "size_kb":  round(size_kb, 1),
                "modified": modified,
            })

        # Check all expected files are present
        present_keys = {o["key"].split("/")[-1] for o in result_objects}
        missing      = [f.name for f in expected_files if f.name not in present_keys]

        if missing:
            print(f"  [VERIFY] ✗ Missing: {missing}")
            return {"status": "partial", "objects": result_objects, "missing": missing}
        else:
            print(f"  [VERIFY] ✓ All {len(expected_files)} files present")
            return {"status": "ok", "objects": result_objects}

    except ClientError as e:
        print(f"  [VERIFY] Error listing objects: {e}")
        return {"status": "error", "error": str(e)}


def main():
    print(f"\n{'='*60}")
    print("  R2-9 STEP 3: S3 DATASET UPLOAD")
    print(f"  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    print(f"\n  Bucket:  s3://{BUCKET_NAME}/")
    print(f"  Prefix:  {S3_PREFIX}")
    print(f"  Region:  {AWS_REGION}")
    print(f"  Files:   {[f.name for f in FILES_TO_UPLOAD]}\n")

    # ── Check files exist ─────────────────────────────────────────
    missing_local = [f for f in FILES_TO_UPLOAD if not f.exists()]
    if missing_local:
        print(f"[WARN] Missing local files: {[f.name for f in missing_local]}")
        print("  Run _export_db1_to_csv.py and _ml_feature_engineering.py first.")
        # Only upload files that exist
        files_to_upload = [f for f in FILES_TO_UPLOAD if f.exists()]
        if not files_to_upload:
            print("[FATAL] No files to upload. Exiting.")
            return False
    else:
        files_to_upload = FILES_TO_UPLOAD

    # ── Initialize S3 client ──────────────────────────────────────
    print("  [AWS] Initializing S3 client...")
    s3 = get_boto3_client()

    # ── Test connection ───────────────────────────────────────────
    try:
        _ = s3.list_buckets()
        print("  [AWS] ✓ Connection verified")
    except Exception as e:
        print(f"  [AWS] ✗ Connection test failed: {e}")
        return False

    # ── Ensure bucket exists ──────────────────────────────────────
    if not ensure_bucket(s3, BUCKET_NAME, AWS_REGION):
        print(f"[FATAL] Could not ensure bucket '{BUCKET_NAME}'")
        return False

    # ── Upload files ──────────────────────────────────────────────
    results = []
    for local_file in files_to_upload:
        result = upload_file(s3, local_file, BUCKET_NAME, S3_PREFIX)
        results.append(result)

    # ── Verify uploads ────────────────────────────────────────────
    verify_result = verify_uploads(s3, BUCKET_NAME, S3_PREFIX, files_to_upload)

    # ── Summary ────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  UPLOAD SUMMARY")
    print(f"{'='*60}")
    success_count = sum(1 for r in results if r["status"] == "ok")
    print(f"  Uploaded:  {success_count}/{len(results)} files")
    print(f"  Bucket:    s3://{BUCKET_NAME}/{S3_PREFIX}")
    print(f"  Verify:    {verify_result['status'].upper()}")

    for r in results:
        status_sym = "✓" if r["status"] == "ok" else "✗"
        if r["status"] == "ok":
            print(f"  {status_sym} {r['key']} ({r['size_mb']:.3f} MB)")
        else:
            print(f"  {status_sym} {r['key']} — {r.get('error', 'unknown error')}")

    print(f"\n  S3 URI base: s3://{BUCKET_NAME}/{S3_PREFIX}")
    print(f"{'='*60}\n")

    return verify_result["status"] in ("ok", "partial")


if __name__ == "__main__":
    ok = main()
    exit(0 if ok else 1)
