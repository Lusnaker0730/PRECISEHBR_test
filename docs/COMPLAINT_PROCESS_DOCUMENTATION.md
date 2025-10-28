# Complaint Process Documentation

**ONC Compliance:** 45 CFR 170.523 (n) - Complaint Process  
**Application:** SMART on FHIR PRECISE-HBR Calculator  
**Document Version:** 1.0  
**Last Updated:** October 2, 2025

---

## Purpose

This document describes the formal complaint intake, tracking, and reporting process for the SMART on FHIR PRECISE-HBR Calculator application, as required by the Office of the National Coordinator for Health IT (ONC) certification criteria.

---

## Regulatory Requirement

**45 CFR 170.523 (n) - Complaint Process**

> "Submit a list of complaints received to the National Coordinator on a quarterly basis each calendar year that includes the number of complaints received, the nature/substance of each complaint, and the type of complainant for each complaint."

---

## Complaint Definition

For the purposes of this process, a "complaint" is defined as any formal feedback, concern, or issue reported by users regarding:

1. **Safety Concerns** - Potential medical errors, patient safety risks, or clinical decision support inaccuracies
2. **Functionality Problems** - Software bugs, calculation errors, or feature malfunctions
3. **Privacy or Security Issues** - Concerns about data protection, unauthorized access, or HIPAA compliance
4. **Usability Concerns** - Difficulties using the application that impact clinical workflow
5. **Accessibility Issues** - Barriers for users with disabilities
6. **Data Accuracy** - Incorrect patient data retrieval or display
7. **Performance Issues** - Application slowness or unavailability
8. **Documentation** - Inadequate or unclear user instructions

---

## Complaint Intake Process

### 1. How Users Submit Complaints

**Primary Method:** Web-based complaint form

- **URL:** `[Application Base URL]/report-issue`
- **Access:** Available from the main navigation menu ("Report Issue" link)
- **Availability:** 24/7, no authentication required (to allow reporting of login issues)

**Information Collected:**
- Complainant type (clinician, patient, administrator, developer, other)
- Issue category (safety, functionality, privacy, usability, accessibility, data accuracy, performance, documentation, other)
- Severity level (critical, high, medium, low)
- Brief description (subject line)
- Detailed description
- Contact email (optional)
- Timestamp and unique reference ID (auto-generated)

**Privacy Protection:**
- Form explicitly warns users NOT to include Protected Health Information (PHI)
- Users must acknowledge they have not included PHI before submission
- All submissions are logged without PHI

### 2. Alternative Complaint Channels

**Email:** safety@yourdomain.com (for urgent safety concerns)  
**Phone:** [Your Support Phone Number] (for critical issues requiring immediate attention)

---

## Complaint Storage and Tracking

### Storage Location

All complaints are stored in:
```
instance/complaints/complaints.jsonl
```

### Storage Format

Complaints are stored in JSON Lines format (one JSON object per line), which allows for:
- Easy appending of new complaints
- Simple parsing and analysis
- Version control friendly
- No database dependency

### Data Retention

- **Retention Period:** Minimum 3 years from the date of submission
- **Backup:** Complaints file is included in regular application backups
- **Access Control:** Limited to authorized personnel only

### Complaint Reference IDs

Each complaint is assigned a unique reference ID in the format:
```
COMP-YYYYMMDD-XXXXXXXX

Example: COMP-20251002-A3B7F91C
```

Where:
- `COMP` = Complaint identifier
- `YYYYMMDD` = Date of submission
- `XXXXXXXX` = 8-character unique identifier

---

## Complaint Review and Response

### Review Timeline

| Severity | Initial Review | Investigation | Response |
|:---|:---|:---|:---|
| **Critical** | Within 4 hours | 1-2 business days | Immediate action + follow-up |
| **High** | Within 24 hours | 3-5 business days | Detailed response |
| **Medium** | Within 3 business days | 1-2 weeks | Standard response |
| **Low** | Within 1 week | As scheduled | Acknowledgment + planned action |

### Review Process

1. **Acknowledgment:** Complainant receives reference ID immediately upon submission
2. **Triage:** Complaint is categorized and assigned severity level
3. **Investigation:** Technical team reviews the issue
4. **Action:** Appropriate remediation or response is determined
5. **Response:** If contact information provided, complainant is notified of findings
6. **Documentation:** All actions and resolutions are logged

### Critical Complaint Escalation

Critical complaints trigger:
- Immediate logging at WARNING level in application logs
- Notification to designated safety officer
- Expedited investigation and resolution
- Potential product recall or field safety notice if warranted

---

## Quarterly Reporting to ONC

### Reporting Schedule

Quarterly reports are submitted to the Office of the National Coordinator for Health IT within **30 days** of the end of each calendar quarter:

- **Q1 (Jan-Mar):** Report due by April 30
- **Q2 (Apr-Jun):** Report due by July 31
- **Q3 (Jul-Sep):** Report due by October 31
- **Q4 (Oct-Dec):** Report due by January 31

### Report Generation

Reports are generated using the `complaint_manager.py` tool:

```bash
python complaint_manager.py report 2025 4
```

This generates a comprehensive report including:
1. **Total number of complaints** received during the quarter
2. **Breakdown by category** (nature/substance of each complaint)
3. **Breakdown by complainant type**
4. **Breakdown by severity**
5. **Detailed list** of all complaints with reference IDs

### Report Contents (Required by ONC)

Per 45 CFR 170.523 (n), each quarterly report includes:

✅ **Number of complaints received**  
✅ **Nature/substance of each complaint** (category)  
✅ **Type of complainant for each complaint**

### Report Distribution

Quarterly reports are:
1. Saved to `instance/complaints/reports/onc_complaint_report_YYYY_QX.txt`
2. Submitted to ONC via their designated submission portal
3. Made available for public review (as required by Epic)
4. Archived for regulatory compliance

---

## Complaint Management Tools

### Command-Line Tool: `complaint_manager.py`

**List all complaints:**
```bash
python complaint_manager.py list
```

**Filter by category and severity:**
```bash
python complaint_manager.py list --category safety --severity critical
```

**Generate quarterly report:**
```bash
python complaint_manager.py report 2025 4
```

**Export to CSV for analysis:**
```bash
python complaint_manager.py export complaints_2025.csv
```

---

## Metrics and Analysis

### Key Performance Indicators (KPIs)

The following metrics are tracked:
- Total complaints per quarter
- Average resolution time by severity
- Complaint category distribution
- Repeat complaints (same issue reported multiple times)
- Percentage of complaints resolved
- User satisfaction with resolution (if feedback provided)

### Continuous Improvement

Complaint data is reviewed quarterly to:
1. Identify recurring issues requiring systemic fixes
2. Prioritize feature improvements and bug fixes
3. Improve user documentation and training
4. Enhance application safety and quality

---

## Public Accessibility

Per ONC requirements and Epic Developer Terms, this complaint process documentation is:

- ✅ Publicly accessible in the application's GitHub repository
- ✅ Linked from the application's documentation page
- ✅ Referenced in the ONC compliance certification documentation

**Public Documentation URL:**  
`https://github.com/[your-org]/[your-repo]/blob/main/COMPLAINT_PROCESS_DOCUMENTATION.md`

---

## Contact Information

**Complaint Submission:**  
Web Form: `[Application Base URL]/report-issue`  
Email: safety@yourdomain.com  
Phone: [Your Support Phone Number]

**Responsible Party:**  
[Your Name / Organization Name]  
[Your Title]  
[Your Contact Email]

**ONC Reporting Officer:**  
[Name of person responsible for ONC submissions]  
[Contact Information]

---

## Revision History

| Version | Date | Author | Changes |
|:---|:---|:---|:---|
| 1.0 | 2025-10-02 | Development Team | Initial complaint process documentation |

---

## Appendix A: Sample Complaint Form Fields

**Required Fields:**
- Complainant Type (dropdown)
- Issue Category (dropdown)
- Severity (dropdown)
- Brief Description (text, max 200 chars)
- Detailed Description (textarea)
- Acknowledgment checkbox (confirming no PHI included)

**Optional Fields:**
- Contact Email

**Auto-Generated Fields:**
- Reference ID
- Timestamp
- User Agent
- IP Address (for security purposes, not included in ONC reports)

---

## Appendix B: Complaint Categories

| Category | Description | Examples |
|:---|:---|:---|
| Safety | Potential medical errors or patient safety risks | Incorrect risk calculation, missing critical data |
| Functionality | Software bugs or feature malfunctions | Button not working, page not loading |
| Privacy | Privacy or security concerns | Unauthorized data access, session not expiring |
| Usability | Difficulties using the application | Confusing interface, unclear instructions |
| Accessibility | Barriers for users with disabilities | No screen reader support, poor color contrast |
| Data Accuracy | Incorrect data retrieval or display | Wrong patient data shown, outdated information |
| Performance | Application slowness or unavailability | Slow page load, timeout errors |
| Documentation | Inadequate or unclear user instructions | Missing help text, unclear error messages |
| Other | Any other concerns | General feedback, feature requests |

---

**This complaint process is maintained in compliance with 45 CFR 170.523 (n) and is subject to periodic review and updates.**

