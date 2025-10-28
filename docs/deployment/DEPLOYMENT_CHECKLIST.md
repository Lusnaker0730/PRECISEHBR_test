# Google Cloud Deployment Checklist

## ✅ Pre-Deployment Steps

### 1. Create Google Cloud Secret for FLASK_SECRET_KEY

Run this command to create the secret:

```bash
# Generate a secure secret and store it in Secret Manager
python -c "import secrets; print(secrets.token_urlsafe(32))" > temp_secret.txt
gcloud secrets create FLASK_SECRET_KEY --data-file=temp_secret.txt --replication-policy="automatic"
rm temp_secret.txt
```

Or if the secret already exists, update it:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))" | gcloud secrets versions add FLASK_SECRET_KEY --data-file=-
```

### 2. Grant Secret Access to App Engine

```bash
# Get your project number
PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) --format="value(projectNumber)")

# Grant Secret Manager Secret Accessor role
gcloud secrets add-iam-policy-binding FLASK_SECRET_KEY \
    --member="serviceAccount:${PROJECT_NUMBER}@appspot.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

### 3. Verify Critical Files Exist

Run this command to check all required files:

```bash
# Check for required JSON files
@echo off
echo Checking critical files...
if exist arc-hbr-model.json (echo ✓ arc-hbr-model.json) else (echo ✗ arc-hbr-model.json MISSING)
if exist cdss_config.json (echo ✓ cdss_config.json) else (echo ✗ cdss_config.json MISSING)
if exist bleeding_diathesis_valueset.json (echo ✓ bleeding_diathesis_valueset.json) else (echo ✗ bleeding_diathesis_valueset.json MISSING)
if exist cancer_snomed_valueset.json (echo ✓ cancer_snomed_valueset.json) else (echo ✗ cancer_snomed_valueset.json MISSING)
if exist portal_hypertension_valueset.json (echo ✓ portal_hypertension_valueset.json) else (echo ✗ portal_hypertension_valueset.json MISSING)
if exist prior_bleeding_valueset.json (echo ✓ prior_bleeding_valueset.json) else (echo ✗ prior_bleeding_valueset.json MISSING)
```

### 4. Review app.yaml Configuration

Ensure your `app.yaml` has correct settings:

- ✅ `FLASK_SECRET_KEY` points to Secret Manager
- ✅ `SMART_CLIENT_ID` is set (currently hardcoded)
- ✅ `SMART_REDIRECT_URI` matches your deployed URL
- ✅ `APP_BASE_URL` matches your deployed URL

## 🚀 Deployment Commands

### Test What Will Be Deployed

```bash
# Preview files that will be uploaded
gcloud app deploy --no-promote --no-stop-previous-version --verbosity=debug
```

### Deploy to Google Cloud

```bash
# Deploy to App Engine
gcloud app deploy app.yaml

# View logs after deployment
gcloud app logs tail -s default
```

### Monitor Deployment

```bash
# Check application status
gcloud app browse

# View recent logs
gcloud app logs read --limit=50

# Stream live logs
gcloud app logs tail -s default
```

## ⚠️ Known Issues

### Issue 1: FLASK_SECRET_KEY Access Error
**Error**: `Failed to access secret for FLASK_SECRET_KEY at path 'projects/smart-ui/secrets/FLASK_SECRET_KEY/versions/latest'`

**Solution**: Make sure you've:
1. Created the secret (Step 1 above)
2. Granted IAM permissions (Step 2 above)
3. Verified the project ID in app.yaml matches your GCP project

### Issue 2: Missing arc-hbr-model.json
**Error**: `File not found: arc-hbr-model.json`

**Solution**: The file was created by the assistant. Verify it exists:
```bash
dir arc-hbr-model.json
```

### Issue 3: TypeErrors with FHIR timeout
**Status**: ✅ FIXED - timeout parameters removed from fhir_data_service.py

## 📝 Post-Deployment Verification

After deployment, test these endpoints:

1. **Landing Page**: `https://smart-lu.uc.r.appspot.com/`
2. **Launch Endpoint**: `https://smart-lu.uc.r.appspot.com/launch`
3. **Callback Endpoint**: `https://smart-lu.uc.r.appspot.com/callback`
4. **Tradeoff Analysis**: `https://smart-lu.uc.r.appspot.com/tradeoff_analysis`

## 🔒 Security Notes

- The `.env` file is excluded from deployment (this is correct)
- Secrets are managed through Google Cloud Secret Manager
- HTTPS is enforced via `secure: always` in app.yaml
- Session files are stored in `instance/flask_session` directory

## 📞 Support

If you encounter issues:
1. Check logs: `gcloud app logs tail -s default`
2. Verify secrets: `gcloud secrets list`
3. Check IAM permissions: `gcloud secrets get-iam-policy FLASK_SECRET_KEY`

