# GitHub Actions CI/CD Workflows

This directory contains GitHub Actions workflows for the PRECISE-HBR SMART on FHIR application.

## 📋 Available Workflows

### 1. **CI - Continuous Integration** (`ci.yml`)

**Triggers:**
- Push to `main`, `PRECISE-HBR`, `PreciseDAPT`, `develop` branches
- Pull requests to `main`, `PRECISE-HBR`, `PreciseDAPT` branches

**Jobs:**
- **Code Quality Checks**: Black formatting, flake8, pylint
- **Security Scan**: Bandit security analysis, pip-audit
- **Tests**: Unit tests with pytest and coverage reporting
- **Build**: Application build verification and artifact creation

**Artifacts:**
- Bandit security reports
- pip-audit vulnerability reports
- Test coverage reports
- Build artifacts

---

### 2. **CD - Continuous Deployment** (`cd.yml`)

**Triggers:**
- Push to `main` (production) or `PRECISE-HBR` (staging) branches
- Manual trigger via workflow_dispatch

**Jobs:**
- **Deploy to Staging**: Auto-deploy PRECISE-HBR branch to staging environment
- **Deploy to Production**: Auto-deploy main branch to production environment
- **Rollback**: Automatic rollback on deployment failure

**Environments:**
- **Staging**: `https://staging-smart-fhir-app.appspot.com`
- **Production**: `https://smart-fhir-app.appspot.com`

**Required Secrets:**
- `GCP_PROJECT_ID`: Google Cloud Project ID
- `GCP_SA_KEY`: Google Cloud Service Account Key (JSON)

---

### 3. **Docker Build and Push** (`docker-build.yml`)

**Triggers:**
- Push to `main`, `PRECISE-HBR` branches
- Tags matching `v*`
- Pull requests
- Manual trigger

**Features:**
- Multi-platform builds (linux/amd64, linux/arm64)
- Automatic tagging (branch, PR, semver, SHA)
- Push to GitHub Container Registry (ghcr.io)
- Trivy security scanning
- SBOM generation

**Image Registry:**
- `ghcr.io/[owner]/smart_fhir_app`

---

### 4. **Security Scan** (`security-scan.yml`)

**Triggers:**
- Scheduled daily at 2 AM UTC
- Push to `main`, `PRECISE-HBR` branches (when Python files change)
- Manual trigger

**Scans:**
- **Dependency Scan**: pip-audit, Safety
- **Code Security**: Bandit analysis
- **CodeQL Analysis**: GitHub Advanced Security
- **Secrets Detection**: Gitleaks
- **License Compliance**: pip-licenses

**Artifacts:**
- Security reports (HTML, JSON, CSV)
- License compliance reports

---

## 🚀 Quick Start

### Setting Up CI/CD

1. **Configure GitHub Secrets**

Go to your repository → Settings → Secrets and variables → Actions, and add:

```
GCP_PROJECT_ID: your-gcp-project-id
GCP_SA_KEY: {
  "type": "service_account",
  "project_id": "your-project-id",
  ...
}
```

2. **Enable GitHub Actions**

GitHub Actions should be enabled automatically. Verify by going to the "Actions" tab.

3. **Configure Environments**

Go to Settings → Environments and create:
- `staging`
- `production`

Optional: Add protection rules (required reviewers, wait timer)

---

## 🔐 Required Secrets

### GitHub Secrets

| Secret Name | Description | Required For |
|-------------|-------------|--------------|
| `GCP_PROJECT_ID` | Google Cloud Project ID | CD workflows |
| `GCP_SA_KEY` | Service Account JSON key | CD workflows |
| `GITHUB_TOKEN` | Auto-provided by GitHub | All workflows |

### Service Account Permissions

The GCP Service Account needs these roles:
- `App Engine Admin`
- `Cloud Build Editor`
- `Storage Object Admin`
- `Service Account User`

---

## 🔧 Local Testing

### Test CI Workflow Locally

```bash
# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-cov flake8 black pylint bandit

# Run code quality checks
black --check .
flake8 .
pylint *.py

# Run security scan
bandit -r . -f json -o bandit-report.json --exclude .venv,venv -ll

# Run tests
pytest tests/ --cov=. --cov-report=html
```

### Test Docker Build Locally

```bash
# Build Docker image
docker build -t smart-fhir-app:local .

# Run container
docker run -p 8080:8080 \
  -e FLASK_SECRET_KEY=test-secret \
  smart-fhir-app:local

# Test health endpoint
curl http://localhost:8080/health
```

---

## 📊 Workflow Status Badges

Add these to your README.md:

```markdown
![CI Status](https://github.com/[owner]/smart_fhir_app/workflows/CI/badge.svg)
![Security Scan](https://github.com/[owner]/smart_fhir_app/workflows/Security%20Scan/badge.svg)
![Docker Build](https://github.com/[owner]/smart_fhir_app/workflows/Docker%20Build/badge.svg)
```

---

## 🐛 Troubleshooting

### CI Workflow Fails

**Code Quality Issues:**
```bash
# Auto-fix formatting
black .

# Check specific errors
flake8 . --show-source
```

**Test Failures:**
```bash
# Run tests with verbose output
pytest tests/ -v --tb=long

# Run specific test
pytest tests/test_app_basic.py::test_health_endpoint -v
```

### CD Workflow Fails

**Authentication Issues:**
- Verify `GCP_SA_KEY` is valid JSON
- Check service account has required permissions
- Ensure project ID is correct

**Deployment Issues:**
```bash
# Check App Engine status
gcloud app versions list --project=your-project-id

# View deployment logs
gcloud app logs tail --project=your-project-id
```

### Docker Build Fails

**Build Errors:**
```bash
# Check Dockerfile syntax
docker build --no-cache -t smart-fhir-app:test .

# View build logs
docker build -t smart-fhir-app:test . 2>&1 | tee build.log
```

---

## 📈 Monitoring and Alerts

### View Workflow Runs

Go to: `https://github.com/[owner]/smart_fhir_app/actions`

### Set Up Notifications

1. Go to Settings → Notifications
2. Enable "Actions" notifications
3. Choose notification preferences

---

## 🔄 Workflow Updates

### Modifying Workflows

1. Edit workflow files in `.github/workflows/`
2. Test changes in a feature branch first
3. Create PR for review
4. Merge to main/PRECISE-HBR to activate

### Adding New Workflows

```yaml
name: New Workflow

on:
  push:
    branches: [ main ]

jobs:
  new-job:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run task
        run: echo "Task completed"
```

---

## 📚 Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Google Cloud Deploy with GitHub Actions](https://github.com/google-github-actions)
- [Docker Build Push Action](https://github.com/docker/build-push-action)
- [CodeQL Analysis](https://codeql.github.com/)

---

## 🤝 Contributing

When contributing to CI/CD workflows:

1. Test changes locally first
2. Document any new secrets or configuration
3. Update this README with changes
4. Get review from DevOps team

---

## 📝 Change Log

### v1.0.0 - Initial Setup
- CI workflow with code quality and security checks
- CD workflow with staging and production deployments
- Docker build and push workflow
- Scheduled security scanning
- Comprehensive test suite

