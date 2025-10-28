# HIPAA-Compliant Security Deployment Guide

## Overview

This guide provides comprehensive instructions for securely deploying the SMART on FHIR PRECISE-HBR Calculator application in compliance with HIPAA Security Rule requirements. All identified risks from the Risk Analysis have been mitigated through code changes and deployment practices.

## 🔐 Required Environment Variables

### Essential Security Variables

```bash
# R-01 Mitigation: Strong secret key (required)
FLASK_SECRET_KEY="your-strong-secret-key-here"  # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"

# SMART on FHIR Configuration
SMART_CLIENT_ID="your-client-id"
SMART_REDIRECT_URI="https://your-domain.com/callback"
SMART_CLIENT_SECRET="your-client-secret"  # Optional, depends on your FHIR server
SMART_SCOPES="openid fhirUser launch/patient patient/*.read"

# R-08 Mitigation: Production environment flag
PRODUCTION="true"  # or FLASK_ENV="production"

# Optional: Google Cloud Secret Manager (for production)
# FLASK_SECRET_KEY="projects/your-project/secrets/flask-secret-key/versions/latest"
```

### Development vs Production

```bash
# Development Environment
FLASK_DEBUG="true"      # Only in development!
FLASK_ENV="development"

# Production Environment  
FLASK_ENV="production"  # Required for production
PRODUCTION="true"       # Additional production flag
# FLASK_DEBUG should NOT be set or should be "false"
```

## 🛡️ Security Features Implemented

### R-01: Session Forgery Prevention
- **Implementation**: Mandatory `FLASK_SECRET_KEY` environment variable
- **Code Location**: `APP.py` lines 67-72
- **Verification**: Application will fail to start if `FLASK_SECRET_KEY` is not set

### R-02: Access Token Protection
- **Implementation**: Secure filesystem permissions (0o700) for session directory
- **Code Location**: `config.py` lines 43-57
- **Verification**: Session directory automatically created with secure permissions

### R-03: ePHI Logging Protection
- **Implementation**: Custom logging filter to scrub ePHI from logs
- **Code Location**: `logging_filter.py` and `APP.py` lines 79-86
- **Features**:
  - Automatic redaction of patient IDs, names, dates of birth
  - Access token sanitization
  - Medical record number protection
  - Phone number and email redaction

### R-04: Frontend ePHI Protection
- **Implementation**: Security warnings and session timeout
- **Code Location**: `templates/main.html` lines 25-38 and 192-278
- **Features**:
  - Security advisory banner
  - 30-minute automatic session timeout
  - User activity detection
  - Session warning at 5 minutes remaining

### R-05: External Service Resilience
- **Implementation**: Enhanced timeout handling and error messages
- **Code Location**: `APP.py` lines 137-168
- **Features**:
  - Specific error handling for timeouts, connection issues
  - User-friendly error messages
  - Appropriate HTTP status codes

### R-07: Supply Chain Security
- **Implementation**: Pinned dependency versions
- **Code Location**: `requirements.txt`
- **Verification**: All dependencies use specific version numbers

### R-08: Production Security
- **Implementation**: Strict production environment checks
- **Code Location**: `APP.py` lines 377-412
- **Features**:
  - Debug mode prohibited in production
  - Multiple production environment detection methods
  - Enhanced logging for security events

## 🚀 Deployment Instructions

### 1. Environment Setup

#### Generate Strong Secret Key
```bash
python -c "import secrets; print('FLASK_SECRET_KEY=' + secrets.token_urlsafe(32))"
```

#### Set Environment Variables
```bash
# Linux/Mac
export FLASK_SECRET_KEY="your-generated-secret-key"
export SMART_CLIENT_ID="your-client-id"
export SMART_REDIRECT_URI="https://your-domain.com/callback"
export PRODUCTION="true"

# Windows
set FLASK_SECRET_KEY=your-generated-secret-key
set SMART_CLIENT_ID=your-client-id
set SMART_REDIRECT_URI=https://your-domain.com/callback
set PRODUCTION=true
```

### 2. Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Verify security dependencies
pip list | grep -E "(Flask-Talisman|bandit|pip-audit)"
```

### 3. Security Verification

#### Run Security Scans
```bash
# Check for vulnerabilities in dependencies
pip-audit

# Static security analysis
bandit -r . -x ./locustfile.py,./extract_session_info.py,./generate_performance_comparison.py

# Test ePHI logging filter
python logging_filter.py
```

#### Verify Session Directory Permissions
```bash
# Check session directory permissions
ls -la instance/flask_session/  # Should show drwx------ (700)
```

### 4. Production Deployment Options

#### Option A: Gunicorn (Recommended)
```bash
# Install gunicorn
pip install gunicorn

# Run with production settings
gunicorn -w 4 -b 0.0.0.0:8080 --timeout 120 APP:app
```

#### Option B: Docker Deployment
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Set production environment
ENV PRODUCTION=true
ENV FLASK_ENV=production

# Create secure session directory
RUN mkdir -p instance/flask_session && chmod 700 instance/flask_session

EXPOSE 8080
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8080", "--timeout", "120", "APP:app"]
```

#### Option C: Google App Engine
```yaml
# app.yaml
runtime: python39

env_variables:
  PRODUCTION: "true"
  FLASK_ENV: "production"
  FLASK_SECRET_KEY: "projects/your-project/secrets/flask-secret-key/versions/latest"
  SMART_CLIENT_ID: "projects/your-project/secrets/smart-client-id/versions/latest"
  SMART_REDIRECT_URI: "https://your-app.appspot.com/callback"

automatic_scaling:
  min_instances: 1
  max_instances: 10
```

## 🔍 Security Monitoring

### Log Monitoring
```bash
# Monitor for security events
tail -f /var/log/your-app.log | grep -E "(SECURITY|ERROR|WARNING)"

# Check for ePHI redaction
grep "REDACTED" /var/log/your-app.log
```

### Health Checks
```bash
# Basic application health
curl -f http://localhost:8080/

# Security headers check
curl -I http://localhost:8080/ | grep -E "(Strict-Transport-Security|Content-Security-Policy)"
```

## 🚨 Security Incident Response

### If ePHI Exposure is Suspected

1. **Immediate Actions**:
   - Stop the application immediately
   - Preserve logs for analysis
   - Document the incident

2. **Investigation**:
   - Check logs for ePHI patterns
   - Verify logging filter is working
   - Review access logs

3. **Mitigation**:
   - Update logging filters if needed
   - Restart application with fixes
   - Monitor for additional issues

### If Unauthorized Access is Detected

1. **Immediate Actions**:
   - Revoke all active sessions
   - Change secret keys
   - Review access logs

2. **Investigation**:
   - Check for session forgery attempts
   - Verify HTTPS usage
   - Review authentication logs

## 📋 Security Checklist

### Pre-Deployment Checklist

- [ ] `FLASK_SECRET_KEY` environment variable is set with strong key
- [ ] `PRODUCTION=true` environment variable is set
- [ ] All dependencies are pinned to specific versions
- [ ] Security scans (bandit, pip-audit) pass
- [ ] Session directory permissions are 700
- [ ] HTTPS is configured and enforced
- [ ] Security headers are enabled (Talisman)
- [ ] ePHI logging filter is active
- [ ] Debug mode is disabled in production

### Post-Deployment Verification

- [ ] Application starts without security warnings
- [ ] Session timeout works correctly (30 minutes)
- [ ] Security advisory banner is displayed
- [ ] Error messages don't expose ePHI
- [ ] Logs are properly sanitized
- [ ] External service timeouts are handled gracefully
- [ ] FHIR server connectivity is working

## 🔧 Troubleshooting

### Common Issues

**Issue**: "FLASK_SECRET_KEY environment variable is required"
**Solution**: Set the environment variable with a strong secret key

**Issue**: Session directory permission errors
**Solution**: Ensure the application user has write access to the parent directory

**Issue**: ePHI appearing in logs
**Solution**: Verify logging filter is installed and test with `python logging_filter.py`

**Issue**: Session timeout not working
**Solution**: Check browser console for JavaScript errors, verify session timer is starting

## 📚 References

- [HIPAA Security Rule](https://www.hhs.gov/hipaa/for-professionals/security/index.html)
- [SMART on FHIR Security](http://hl7.org/fhir/smart-app-launch/1.0.0/index.html#security-considerations)
- [Flask Security Best Practices](https://flask.palletsprojects.com/en/2.3.x/security/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)

---

**Document Version**: 1.0  
**Last Updated**: 2025-09-29  
**Next Review**: 2025-12-29
