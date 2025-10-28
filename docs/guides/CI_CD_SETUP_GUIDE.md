# CI/CD Setup Guide for PRECISE-HBR SMART on FHIR Application

Complete guide for setting up Continuous Integration and Continuous Deployment for the PRECISE-HBR application.

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [GitHub Repository Setup](#github-repository-setup)
3. [Google Cloud Platform Setup](#google-cloud-platform-setup)
4. [GitHub Actions Configuration](#github-actions-configuration)
5. [Environment Configuration](#environment-configuration)
6. [Testing the Pipeline](#testing-the-pipeline)
7. [Troubleshooting](#troubleshooting)

---

## 1. Prerequisites

### Required Accounts
- ✅ GitHub account with repository access
- ✅ Google Cloud Platform account
- ✅ GCP Project with billing enabled

### Required Tools
```bash
# Install gcloud CLI
curl https://sdk.cloud.google.com | bash

# Install Docker
# See: https://docs.docker.com/get-docker/

# Install Git
# See: https://git-scm.com/downloads
```

---

## 2. GitHub Repository Setup

### Step 1: Clone the Repository

```bash
git clone https://github.com/Lusnaker0730/smart_fhir_app.git
cd smart_fhir_app
```

### Step 2: Verify Workflow Files

Check that workflow files exist:

```bash
ls -la .github/workflows/
# Should see: ci.yml, cd.yml, docker-build.yml, security-scan.yml
```

### Step 3: Enable GitHub Actions

1. Go to repository on GitHub
2. Click **"Actions"** tab
3. Click **"I understand my workflows, go ahead and enable them"**

---

## 3. Google Cloud Platform Setup

### Step 1: Create GCP Project

```bash
# Set your project ID
export PROJECT_ID="smart-fhir-app-prod"

# Create project
gcloud projects create $PROJECT_ID --name="PRECISE-HBR SMART FHIR App"

# Set as active project
gcloud config set project $PROJECT_ID

# Enable billing (must be done via console)
echo "Enable billing at: https://console.cloud.google.com/billing/linkedaccount?project=$PROJECT_ID"
```

### Step 2: Enable Required APIs

```bash
# Enable App Engine API
gcloud services enable appengine.googleapis.com

# Enable Cloud Build API
gcloud services enable cloudbuild.googleapis.com

# Enable Container Registry API
gcloud services enable containerregistry.googleapis.com

# Enable Secret Manager API
gcloud services enable secretmanager.googleapis.com

# Enable Logging API
gcloud services enable logging.googleapis.com
```

### Step 3: Initialize App Engine

```bash
# Create App Engine application
gcloud app create --region=us-central1

# Verify
gcloud app describe
```

### Step 4: Create Service Account

```bash
# Create service account
gcloud iam service-accounts create github-actions-deployer \
    --display-name="GitHub Actions Deployer" \
    --description="Service account for GitHub Actions deployments"

# Get service account email
export SA_EMAIL="github-actions-deployer@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant necessary roles
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/appengine.appAdmin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/cloudbuild.builds.editor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/iam.serviceAccountUser"
```

### Step 5: Create Service Account Key

```bash
# Create and download key
gcloud iam service-accounts keys create ~/gcp-key.json \
    --iam-account=$SA_EMAIL

# View key (you'll need this for GitHub)
cat ~/gcp-key.json

# ⚠️ IMPORTANT: Keep this key secure and never commit it to Git!
```

---

## 4. GitHub Actions Configuration

### Step 1: Add GitHub Secrets

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **"New repository secret"**

Add these secrets:

#### `GCP_PROJECT_ID`
```
Value: smart-fhir-app-prod
```

#### `GCP_SA_KEY`
```
Value: [Paste entire contents of ~/gcp-key.json]
```

### Step 2: Create GitHub Environments

1. Go to **Settings** → **Environments**
2. Click **"New environment"**

#### Create "staging" Environment
- Name: `staging`
- Protection rules (optional):
  - ☑️ Required reviewers: 0
  - ☑️ Wait timer: 0 minutes

#### Create "production" Environment
- Name: `production`
- Protection rules (recommended):
  - ☑️ Required reviewers: 1 (add yourself)
  - ☑️ Wait timer: 5 minutes

### Step 3: Configure Branch Protection

1. Go to **Settings** → **Branches**
2. Add rule for `main` branch:
   - ☑️ Require pull request reviews before merging
   - ☑️ Require status checks to pass before merging
     - Select: `Code Quality Checks`, `Security Scan`, `Build`
   - ☑️ Require branches to be up to date before merging

---

## 5. Environment Configuration

### Step 1: Update app.yaml

Edit `app.yaml` with your configuration:

```yaml
runtime: python311
entrypoint: gunicorn -b :$PORT --timeout 120 APP:app

env_variables:
  FLASK_ENV: 'production'
  FLASK_SECRET_KEY: 'projects/${PROJECT_ID}/secrets/flask-secret-key/versions/latest'
  SMART_CLIENT_ID: 'projects/${PROJECT_ID}/secrets/smart-client-id/versions/latest'
  SMART_CLIENT_SECRET: 'projects/${PROJECT_ID}/secrets/smart-client-secret/versions/latest'
  SMART_REDIRECT_URI: 'https://smart-fhir-app.appspot.com/callback'
  # Add your EHR configuration
```

### Step 2: Create Secrets in Secret Manager

```bash
# Create Flask secret key
echo -n "$(openssl rand -base64 32)" | \
gcloud secrets create flask-secret-key \
    --data-file=- \
    --replication-policy="automatic"

# Create SMART client ID secret
echo -n "your-smart-client-id" | \
gcloud secrets create smart-client-id \
    --data-file=- \
    --replication-policy="automatic"

# Create SMART client secret
echo -n "your-smart-client-secret" | \
gcloud secrets create smart-client-secret \
    --data-file=- \
    --replication-policy="automatic"

# Grant App Engine access to secrets
export APP_ENGINE_SA="${PROJECT_ID}@appspot.gserviceaccount.com"

gcloud secrets add-iam-policy-binding flask-secret-key \
    --member="serviceAccount:${APP_ENGINE_SA}" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding smart-client-id \
    --member="serviceAccount:${APP_ENGINE_SA}" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding smart-client-secret \
    --member="serviceAccount:${APP_ENGINE_SA}" \
    --role="roles/secretmanager.secretAccessor"
```

---

## 6. Testing the Pipeline

### Test 1: CI Workflow (Push to Feature Branch)

```bash
# Create feature branch
git checkout -b feature/test-ci

# Make a small change
echo "# Test CI" >> README.md

# Commit and push
git add README.md
git commit -m "Test CI workflow"
git push origin feature/test-ci
```

**Expected Result:**
- ✅ Code quality checks run
- ✅ Security scan completes
- ✅ Tests execute
- ✅ Build succeeds
- ✅ Artifacts uploaded

### Test 2: PR Workflow

```bash
# Create pull request on GitHub
# Go to: https://github.com/[owner]/smart_fhir_app/pull/new/feature/test-ci
```

**Expected Result:**
- ✅ All CI checks pass
- ✅ Status checks appear on PR
- ✅ Required reviews enforced

### Test 3: Staging Deployment (PRECISE-HBR branch)

```bash
# Switch to PRECISE-HBR branch
git checkout PRECISE-HBR

# Merge your feature
git merge feature/test-ci

# Push
git push origin PRECISE-HBR
```

**Expected Result:**
- ✅ CI workflow runs
- ✅ CD workflow triggers
- ✅ Deploys to staging environment
- ✅ Health checks pass

Verify deployment:
```bash
curl https://staging-smart-fhir-app.appspot.com/health
```

### Test 4: Production Deployment (main branch)

```bash
# Switch to main branch
git checkout main

# Merge PRECISE-HBR
git merge PRECISE-HBR

# Push
git push origin main
```

**Expected Result:**
- ✅ CI workflow runs
- ✅ CD workflow triggers
- ✅ Requires approval (if configured)
- ✅ Deploys to production
- ✅ Health checks pass

Verify deployment:
```bash
curl https://smart-fhir-app.appspot.com/health
```

### Test 5: Docker Build

```bash
# Tag a new version
git tag v1.0.0
git push origin v1.0.0
```

**Expected Result:**
- ✅ Docker image builds
- ✅ Multi-platform support
- ✅ Pushed to ghcr.io
- ✅ Security scan runs
- ✅ SBOM generated

View image:
```bash
docker pull ghcr.io/[owner]/smart_fhir_app:v1.0.0
```

---

## 7. Troubleshooting

### Common Issues

#### Issue: "Permission Denied" during deployment

**Solution:**
```bash
# Verify service account roles
gcloud projects get-iam-policy $PROJECT_ID \
    --flatten="bindings[].members" \
    --filter="bindings.members:serviceAccount:$SA_EMAIL"

# Add missing roles if needed
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/appengine.appAdmin"
```

#### Issue: "API not enabled"

**Solution:**
```bash
# Enable all required APIs
gcloud services enable appengine.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable secretmanager.googleapis.com
```

#### Issue: "Invalid service account key"

**Solution:**
1. Verify JSON format in GitHub secret
2. Ensure no extra whitespace or line breaks
3. Regenerate key if needed:
```bash
gcloud iam service-accounts keys create ~/new-key.json \
    --iam-account=$SA_EMAIL
```

#### Issue: Tests fail in CI

**Solution:**
```bash
# Run tests locally
pip install -r requirements.txt
pip install pytest pytest-cov

# Run with verbose output
pytest tests/ -v --tb=long

# Check for import errors
python -c "from APP import app; print('OK')"
```

#### Issue: Docker build fails

**Solution:**
```bash
# Test build locally
docker build -t test-build .

# Check for syntax errors
docker build --no-cache -t test-build . 2>&1 | grep -i error

# Verify requirements.txt
pip install -r requirements.txt
```

---

## 📊 Monitoring

### View Workflow Runs

```bash
# Using GitHub CLI
gh run list

# View specific run
gh run view [run-id]
```

### View Deployment Logs

```bash
# App Engine logs
gcloud app logs tail --project=$PROJECT_ID

# View specific version
gcloud app logs read --project=$PROJECT_ID --version=[version-id]
```

### Health Checks

```bash
# Staging
curl https://staging-smart-fhir-app.appspot.com/health

# Production
curl https://smart-fhir-app.appspot.com/health
```

---

## 🔐 Security Best Practices

1. **Never commit secrets to Git**
   - Use GitHub Secrets for sensitive data
   - Use GCP Secret Manager for application secrets

2. **Rotate credentials regularly**
   ```bash
   # Rotate service account key every 90 days
   gcloud iam service-accounts keys create ~/new-key.json \
       --iam-account=$SA_EMAIL
   ```

3. **Use least privilege principle**
   - Only grant necessary roles
   - Use separate service accounts for different environments

4. **Enable audit logging**
   ```bash
   gcloud logging read "resource.type=gae_app" --limit 10
   ```

5. **Monitor security scans**
   - Review Bandit reports weekly
   - Check dependency vulnerabilities
   - Address HIGH severity issues immediately

---

## 📚 Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Google App Engine Python 3](https://cloud.google.com/appengine/docs/standard/python3)
- [SMART on FHIR Specification](http://hl7.org/fhir/smart-app-launch/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)

---

## 🆘 Getting Help

If you encounter issues:

1. Check workflow logs in GitHub Actions
2. Review GCP deployment logs
3. Consult documentation
4. Open an issue in the repository

---

## ✅ Checklist

Use this checklist to verify your setup:

- [ ] GitHub repository cloned
- [ ] Workflow files present in `.github/workflows/`
- [ ] GCP project created and billing enabled
- [ ] Required APIs enabled
- [ ] App Engine initialized
- [ ] Service account created with proper roles
- [ ] Service account key generated
- [ ] GitHub secrets configured (GCP_PROJECT_ID, GCP_SA_KEY)
- [ ] GitHub environments created (staging, production)
- [ ] Branch protection rules set
- [ ] app.yaml configured
- [ ] GCP secrets created in Secret Manager
- [ ] CI workflow tested
- [ ] Staging deployment tested
- [ ] Production deployment tested
- [ ] Docker build tested
- [ ] Health checks passing
- [ ] Security scans reviewed
- [ ] Documentation updated

---

**🎉 Congratulations! Your CI/CD pipeline is now set up and ready to use!**

