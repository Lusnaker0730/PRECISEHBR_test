# HIPAA Security Risk Analysis Report

**Document ID:** HSR-AR-001  
**Version:** 1.0  
**Date:** 2025-09-23

---

## 1. Introduction

### 1.1 Purpose
This document presents the findings of a security risk analysis conducted for the **SMART on FHIR PRECISE-HBR Calculator** application. The purpose of this analysis is to identify, evaluate, and document potential risks and vulnerabilities to the confidentiality, integrity, and availability of electronic Protected Health Information (ePHI) that is processed, transmitted, or handled by the application.

This analysis is a foundational component of the application's compliance with the Health Insurance Portability and Accountability Act (HIPAA) Security Rule (45 C.F.R. Part 160 and Part 164, Subparts A and C).

### 1.2 Scope
The scope of this analysis covers the entire SMART on FHIR PRECISE-HBR Calculator application, including:
-   **Backend Components**: The Flask web application (`APP.py`), data fetching logic (`fhir_data_service.py`), authentication modules (`auth.py`), and configuration files (`config.py`).
-   **Frontend Components**: User interface templates (`templates/main.html`) that render ePHI.
-   **Data Flow**: The transmission of data from the launching Electronic Health Record (EHR) system, to the application, to the FHIR data server, and back to the user's browser.
-   **Exclusions**: This analysis does not cover the security of the underlying EHR, the FHIR server, or the user's end-device and network, which are considered separate entities. However, risks associated with the application's *interaction* with these entities are included.

---

## 2. System Characterization

The **SMART on FHIR PRECISE-HBR Calculator** is a web-based clinical decision support tool. It is launched from within an EHR, retrieves specific patient data from a FHIR server, calculates the PRECISE-HBR bleeding risk score, and displays the results to the clinician in real-time.

A key architectural feature is that the application **does not have its own database** and **does not persistently store ePHI**. Data is held in memory only for the duration of a single user request.

---

## 3. ePHI Identification

The application handles the following categories and types of ePHI:

| Data Category | Specific Data Elements | Source FHIR Resource |
| :--- | :--- | :--- |
| **Demographics** | Patient Name, Age, Gender, Date of Birth | `Patient` |
| **Identifiers** | Patient ID | `Patient` (from Launch Context)|
| **Diagnoses** | Medical history (e.g., prior bleeding) | `Condition` |
| **Lab Results** | eGFR, Creatinine, Hemoglobin, WBC, Platelets | `Observation` |
| **Medications**| Oral Anticoagulants (OAC) history | `MedicationRequest`|

---

## 4. Threat and Vulnerability Identification

The following potential threats and associated vulnerabilities were identified during the analysis:

| Threat | Associated Vulnerability |
| :--- | :--- |
| **Unauthorized Access** | **V-01:** Sensitive information (default `SECRET_KEY`) is hardcoded.<br>**V-02:** Access Tokens are stored in potentially insecure filesystem sessions. |
| **Data Breach** | **V-03:** ePHI may be inadvertently written to system logs during error conditions.<br>**V-04:** ePHI rendered in the frontend may be exposed on insecure user devices/networks. |
| **Service Disruption** | **V-05:** High dependency on external EHR/FHIR services without robust timeout handling.<br>**V-06:** Lack of input validation and rate limiting on public-facing API endpoints. |
| **Supply Chain Attack** | **V-07:** Use of third-party software libraries with unpinned, potentially vulnerable versions. |
| **Insecure Configuration** | **V-08:** Potential for running the application in debug mode in a production environment. |

---

## 5. Current Controls Assessment

The application currently has the following security controls in place, which form a strong security baseline:

-   **Transmission Encryption**: All data in transit is encrypted using HTTPS.
-   **Federated Access Control**: Authentication and authorization are delegated to the source EHR system via the SMART on FHIR protocol. The application does not manage user credentials.
-   **Data Minimization**: The application only requests the specific data points required for the risk calculation.
-   **No Persistent Storage of ePHI**: The application is designed to be stateless and does not store ePHI in any database or file, significantly reducing the risk of a large-scale data breach.
-   **Server-Side Session Management**: Sensitive tokens are stored in server-side sessions, not in the browser, protecting them from XSS attacks.

---

## 6. Risk Assessment Summary

The following matrix summarizes the assessment of each identified risk, taking into account the current controls.

| ID | Risk Description | Likelihood | Impact | **Risk Level (Initial)** |
| :--| :--- | :--- | :--- | :--- |
| R-01 | Session forgery via hardcoded `SECRET_KEY` | Low | High | **Medium** |
| R-02 | Access Token theft from filesystem sessions | Low | High | **Medium** |
| R-03 | ePHI leakage in logs | Medium | Medium | **Medium** |
| R-04 | Frontend ePHI theft (insecure user env) | High | Low | **Medium** |
| R-05 | Service unavailability (external dependency) | High | Low | **Medium** |
| R-06 | Denial of Service (DoS) attack | Medium | Low | **Low** |
| R-07 | Supply chain attack (vulnerable libraries) | Medium | High | **High** |
| R-08 | Information disclosure via debug mode | Low | High | **Medium** |

---

## 7. Conclusion

The risk analysis has identified one **High** risk, six **Medium** risks, and one **Low** risk. While the application's stateless architecture provides significant inherent protection, the identified risks require mitigation to ensure full compliance with the HIPAA Security Rule and to adequately protect ePHI.

A detailed mitigation plan for all High and Medium risks has been documented in the **HIPAA Risk Management Plan (`risk_management_plan.md`)**. Upon successful implementation of the prescribed controls, the residual risk for the application is expected to be low.
