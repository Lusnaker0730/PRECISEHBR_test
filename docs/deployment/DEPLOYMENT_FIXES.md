# Google App Engine Deployment Fixes

## Issue: Read-only Filesystem Error

**Error Message**: `[Errno 30] Read-only file system: 'instance'`

### Root Cause
Google App Engine standard environment has a read-only filesystem except for the `/tmp` directory. The application was trying to write:
1. Flask session files to `instance/flask_session/`
2. Audit logs to `instance/audit/audit_log.jsonl`

### Solution Applied

#### 1. Fixed Session Storage (`config.py`)

**Before:**
```python
SESSION_FILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'flask_session')
```

**After:**
```python
# Determine session directory based on environment
if os.environ.get('GAE_ENV', '').startswith('standard'):
    # Running on Google App Engine - use /tmp
    SESSION_FILE_DIR = '/tmp/flask_session'
else:
    # Running locally - use instance directory
    SESSION_FILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'flask_session')
```

#### 2. Fixed Audit Logging (`audit_logger.py`)

**Changes:**
1. Auto-detect environment and use `/tmp/audit/` on App Engine
2. Added exception handling for read-only filesystem
3. Fall back to console logging when file writes fail

**Key modifications:**
- `__init__()`: Auto-detects App Engine and uses `/tmp/audit/audit_log.jsonl`
- `_initialize_audit_log()`: Catches OSError and continues without file logging
- `_get_last_hash()`: Handles read errors gracefully
- `log_event()`: Falls back to console logging for Cloud Logging integration

### Important Notes

1. **Session Persistence**: 
   - `/tmp` is instance-specific and ephemeral
   - Sessions will be lost when instances restart or scale
   - For production, consider using Memcache or Datastore sessions

2. **Audit Log Persistence**:
   - `/tmp` logs are lost when instances restart
   - Audit entries are still logged to Cloud Logging
   - For production, consider Cloud Storage or Datastore for audit logs

3. **Environment Detection**:
   - Uses `GAE_ENV` environment variable
   - Automatically set by App Engine (e.g., `standard`)

### Testing

**Local Development:**
- Sessions: `instance/flask_session/`
- Audit logs: `instance/audit/audit_log.jsonl`

**App Engine:**
- Sessions: `/tmp/flask_session/`
- Audit logs: `/tmp/audit/audit_log.jsonl` + Cloud Logging

### Future Improvements

For production deployment, consider:

1. **Flask-Session with Memcache:**
   ```python
   SESSION_TYPE = 'memcache'
   SESSION_MEMCACHED = memcache.Client(['127.0.0.1:11211'])
   ```

2. **Audit Logs to Cloud Storage:**
   ```python
   from google.cloud import storage
   # Write audit logs to GCS bucket
   ```

3. **Audit Logs to Cloud Firestore:**
   ```python
   from google.cloud import firestore
   # Store audit entries in Firestore
   ```

### Deployment Command

After these fixes, redeploy with:
```bash
gcloud app deploy app.yaml
```

### Verification

After deployment, check logs:
```bash
gcloud app logs tail -s default --level=info
```

Look for:
- ✅ `Session directory created: /tmp/flask_session`
- ✅ `Audit log initialized: /tmp/audit/audit_log.jsonl`
- ✅ No more "Read-only file system" errors

