# How to Get Session Cookie and Patient ID

This guide will help you obtain the session cookie and patient ID needed for performance testing.

## 方法 1: 通過瀏覽器開發者工具 (Method 1: Browser Developer Tools)

### Step 1: 啟動應用程序 (Start the Application)

1. Make sure your SMART FHIR app is running:
```bash
python APP.py
```

2. Open your browser and go to: `http://localhost:8080`

### Step 2: 完成登入流程 (Complete Login Process)

1. Click on the SMART on FHIR login/launch process
2. Complete the authentication with your FHIR server (e.g., Cerner Sandbox)
3. Make sure you reach the main application page with patient data loaded

### Step 3: 獲取 Session Cookie (Get Session Cookie)

1. **打開開發者工具** (Open Developer Tools):
   - **Chrome/Edge**: Press `F12` or `Ctrl+Shift+I`
   - **Firefox**: Press `F12` or `Ctrl+Shift+I`
   - **Safari**: Press `Cmd+Option+I`

2. **導航到 Application/Storage 標籤** (Navigate to Application/Storage tab):
   - **Chrome/Edge**: Click on "Application" tab
   - **Firefox**: Click on "Storage" tab
   - **Safari**: Click on "Storage" tab

3. **找到 Cookies** (Find Cookies):
   - In the left sidebar, expand "Cookies"
   - Click on `http://localhost:8080` (or your app's URL)

4. **複製 Session Cookie** (Copy Session Cookie):
   - Look for a cookie named `session`
   - Click on the `session` cookie row
   - Copy the "Value" field (this is your session cookie)
   - It will look something like: `eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...`

### Step 4: 獲取 Patient ID (Get Patient ID)

#### 方法 A: 從應用程序界面 (From App Interface)
- Look at your main application page
- The Patient ID is usually displayed on the page
- It might look like: `12345678` or `smart-1234567`

#### 方法 B: 從 Network 標籤 (From Network Tab)
1. In Developer Tools, click on "Network" tab
2. Refresh the page or trigger a risk calculation
3. Look for requests to `/api/calculate_risk`
4. Click on the request and check the "Request Payload"
5. Find the `patientId` field

#### 方法 C: 從 Console (From Console)
1. In Developer Tools, click on "Console" tab
2. Type the following JavaScript code:
```javascript
// Check session storage
console.log('Session Storage:', sessionStorage);
console.log('Local Storage:', localStorage);

// Check if patient ID is in the page
const patientElements = document.querySelectorAll('*');
for (let el of patientElements) {
    if (el.textContent && el.textContent.includes('Patient ID')) {
        console.log('Found Patient ID element:', el.textContent);
    }
}

// Check current URL for patient ID
console.log('Current URL:', window.location.href);
```

## 方法 2: 使用輔助腳本 (Method 2: Using Helper Script)

I've created an interactive helper script to guide you through the process:

```bash
python extract_session_info.py
```

This script will:
1. Guide you through the browser extraction process
2. Test your session cookie to make sure it works
3. Try to automatically extract the Patient ID
4. Test the API endpoint with your credentials
5. Generate the exact environment variable commands you need

### Quick Test Mode

If you already have your session cookie and patient ID, you can test them:

```bash
python extract_session_info.py test "your_session_cookie" "your_patient_id"
```

## 方法 3: 檢查應用程序日誌 (Method 3: Check Application Logs)

When you log into your app, check the console output. You might see:

```
INFO:APP:Received token response: {'access_token': '...', 'patient': 'smart-1234567', ...}
```

The `patient` field contains your Patient ID.

## 故障排除 (Troubleshooting)

### Session Cookie 問題 (Session Cookie Issues)

**Problem**: "Authentication required" error
**Solution**: 
- Make sure you copied the entire session cookie value
- Check that the cookie hasn't expired (log in again if needed)
- Ensure there are no extra spaces or characters

**Problem**: Session cookie is very long
**Solution**: This is normal! SMART on FHIR session cookies can be very long (500+ characters)

### Patient ID 問題 (Patient ID Issues)

**Common Patient ID formats**:
- `smart-1234567` (Cerner Sandbox)
- `12345678` (Simple numeric)
- `Patient/12345` (FHIR resource format - use just the number part)
- `a1b2c3d4-e5f6-7890-abcd-ef1234567890` (UUID format)

**Where to find Patient ID**:
1. **Main app page**: Usually displayed prominently
2. **URL bar**: Sometimes included in the URL after login
3. **Network requests**: Check the payload of API calls
4. **Browser console**: Use the JavaScript code provided above

## 完整示例 (Complete Example)

Here's what your final environment variables should look like:

```bash
# Windows
set LOCUST_SESSION_COOKIE=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJmaGlyX2RhdGEiOnsidG9rZW4iOiJleUpoYkdjaU9pSlNVekkxTmlKOS4uLi4ifQ.abcd1234...
set LOCUST_TEST_PATIENT_ID=smart-1234567
set LOCUST_HOST=http://localhost:8080

# Linux/Mac
export LOCUST_SESSION_COOKIE="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJmaGlyX2RhdGEiOnsidG9rZW4iOiJleUpoYkdjaU9pSlNVekkxTmlKOS4uLi4ifQ.abcd1234..."
export LOCUST_TEST_PATIENT_ID="smart-1234567"
export LOCUST_HOST="http://localhost:8080"
```

## 驗證設置 (Verify Setup)

After setting your environment variables, test them:

```bash
# Test that variables are set
echo %LOCUST_SESSION_COOKIE%     # Windows
echo $LOCUST_SESSION_COOKIE      # Linux/Mac

# Run the quick test
python quick_performance_test.py
```

## 安全注意事項 (Security Notes)

⚠️ **Important**: 
- Session cookies contain sensitive authentication information
- Don't share them or commit them to version control
- They expire after some time, so you may need to get new ones
- Only use them in your local testing environment

## 需要幫助？ (Need Help?)

If you're still having trouble:

1. **Run the interactive helper**:
   ```bash
   python extract_session_info.py
   ```

2. **Check the full guide**: Read `PERFORMANCE_TESTING_GUIDE.md` for more details

3. **Common issues**:
   - Make sure your app is running on the correct port
   - Ensure you've completed the full SMART on FHIR login flow
   - Check that your FHIR server connection is working
   - Verify your browser isn't blocking cookies
