# Quality Management System (QMS) Documentation

**ONC Compliance:** 45 CFR 170.315 (g)(4) - Quality Management System  
**Application:** SMART on FHIR PRECISE-HBR Calculator  
**Document Version:** 1.0  
**Last Updated:** October 2, 2025  
**QMS Standard:** ISO 9001:2015 principles adapted for software development

---

## 1. Executive Summary

This document identifies and describes the Quality Management System (QMS) used in the development, testing, implementation, and maintenance of the SMART on FHIR PRECISE-HBR Calculator application. The QMS ensures that the software meets the highest standards of quality, safety, and regulatory compliance.

**QMS Framework:** This application follows a software development lifecycle based on **ISO 9001:2015** quality management principles and incorporates elements of **IEC 62304** (Medical Device Software Lifecycle) and **Agile** development methodologies.

---

## 2. Quality Management System Overview

### 2.1 QMS Objectives

The QMS for this application aims to:

1. **Ensure Patient Safety**: Guarantee accurate risk calculations and prevent medical errors
2. **Maintain Data Security**: Protect electronic Protected Health Information (ePHI) in compliance with HIPAA
3. **Achieve Regulatory Compliance**: Meet ONC certification criteria and other applicable standards
4. **Deliver High Quality**: Provide reliable, usable, and effective clinical decision support
5. **Enable Continuous Improvement**: Systematically identify and address quality issues

### 2.2 QMS Scope

The QMS covers all phases of the software lifecycle:

- **Requirements Management**: Capturing and tracing clinical and technical requirements
- **Design and Development**: Architecture, coding standards, and design reviews
- **Verification and Validation**: Testing strategies and acceptance criteria
- **Configuration Management**: Version control and change management
- **Problem Resolution**: Bug tracking and issue management
- **Risk Management**: Identification and mitigation of safety and security risks
- **Release Management**: Deployment procedures and post-market surveillance
- **Maintenance and Support**: Updates, patches, and user support

---

## 3. Software Development Lifecycle (SDLC)

### 3.1 Lifecycle Model

This application uses a **hybrid Agile-Waterfall** approach:

- **Agile principles** for iterative development and rapid response to feedback
- **Waterfall elements** for structured documentation and formal verification/validation

### 3.2 Development Phases

#### Phase 1: Requirements Analysis
**Inputs:**
- Clinical guidelines (ARC-HBR, PRECISE-HBR)
- SMART on FHIR specifications
- ONC certification criteria
- HIPAA Security Rule requirements

**Activities:**
- Stakeholder interviews (clinicians, IT staff)
- Requirements elicitation and documentation
- Risk analysis (ISO 14971)
- Requirements traceability matrix creation

**Outputs:**
- Software Requirements Specification (`software_requirements_specification.md`)
- Software Risk Analysis (`software_risk_analysis.md`)
- Risk Management Plan (`risk_management_plan.md`)

**Quality Controls:**
- Requirements review with clinical experts
- Traceability verification
- Compliance mapping to standards

---

#### Phase 2: Design
**Inputs:**
- Approved requirements specifications
- FHIR R4 resource specifications
- C-CDA templates for data export

**Activities:**
- System architecture design
- User interface design and prototyping
- Database schema design
- API endpoint specification
- Security architecture design

**Outputs:**
- System architecture diagrams
- UI/UX mockups and wireframes
- API documentation
- Security design documentation

**Quality Controls:**
- Design review meetings
- Security architecture review
- Usability heuristic evaluation
- Accessibility design checklist (WCAG 2.1)

---

#### Phase 3: Implementation
**Inputs:**
- Approved design specifications
- Coding standards and guidelines

**Activities:**
- Code development in Python (Flask framework)
- Frontend development (HTML, JavaScript, Bootstrap)
- FHIR client integration (`fhirclient` library)
- Security feature implementation
- Documentation (inline comments, docstrings)

**Outputs:**
- Source code (Python, HTML, JavaScript)
- Unit tests
- Integration tests
- Code documentation

**Quality Controls:**
- **Code Reviews**: Peer review of all code changes
- **Static Analysis**: Automated code quality checks
- **Security Scanning**: `bandit` for Python security issues, `pip-audit` for vulnerable dependencies
- **Coding Standards**: PEP 8 compliance for Python
- **Version Control**: Git with meaningful commit messages

**Tools Used:**
- **Version Control**: Git / GitHub
- **Code Quality**: `pylint`, `flake8`
- **Security**: `bandit`, `pip-audit`
- **Dependency Management**: `requirements.txt` with pinned versions

---

#### Phase 4: Verification (Testing)
**Inputs:**
- Implemented software
- Test requirements derived from specifications

**Activities:**
- **Unit Testing**: Test individual functions and modules
- **Integration Testing**: Test component interactions
- **System Testing**: End-to-end testing of complete workflows
- **Regression Testing**: Verify that changes don't break existing functionality
- **Performance Testing**: Load testing and response time validation
- **Security Testing**: Vulnerability scanning and penetration testing

**Outputs:**
- Test cases and test scripts
- Test execution reports
- Bug reports and issue logs
- Test coverage metrics

**Test Documentation:**
- `TEST_REPORT.md` - Comprehensive test results
- `TESTING_METHODOLOGY.md` - Testing approach and strategies
- `RUN_TESTS_GUIDE.md` - Instructions for running tests
- `test_*.py` files - Automated test suites

**Quality Controls:**
- **Test Coverage**: Aim for >80% code coverage
- **Test Traceability**: Map tests back to requirements
- **Automated Testing**: CI/CD integration for automated test execution
- **Independent Testing**: Tests written by different developers than implementation

**Testing Tools:**
- **Test Framework**: `pytest`
- **Coverage Analysis**: `pytest-cov`
- **Performance Testing**: `locust`
- **API Testing**: `requests` library with test assertions

---

#### Phase 5: Validation
**Inputs:**
- Verified software
- User acceptance criteria
- Clinical validation requirements

**Activities:**
- **Clinical Validation**: Verify risk calculation accuracy with known test cases
- **Usability Testing**: Validate with target users (clinicians)
- **SMART on FHIR Validation**: Test with multiple EHR systems
- **Compliance Validation**: Verify ONC criteria compliance
- **User Acceptance Testing (UAT)**: Stakeholder sign-off

**Outputs:**
- Validation reports
- User feedback documentation
- UAT sign-off documentation
- Compliance certification evidence

**Quality Controls:**
- **Clinical Expert Review**: Validation by cardiologists
- **Real-world Testing**: Testing with actual EHR sandboxes (Cerner, Epic)
- **Standards Compliance**: Validation against SMART on FHIR conformance tests

**Validation Evidence:**
- `SMART_HEALTH_IT_TEST_SUMMARY.md` - SMART Health IT Sandbox test results
- `FHIRCLIENT_TESTING_SUMMARY.md` - FHIR client validation
- Clinical calculation validation spreadsheets
- User acceptance testing reports

---

#### Phase 6: Release and Deployment
**Inputs:**
- Validated software
- Deployment environment specifications
- Release notes

**Activities:**
- Release package preparation
- Deployment to production environment
- System configuration and optimization
- Documentation updates
- User training materials preparation

**Outputs:**
- Production deployment
- Deployment guides
- Release notes
- User documentation

**Deployment Documentation:**
- `DEPLOYMENT_GUIDE.md` - General deployment instructions
- `SMART_LU_DEPLOYMENT_GUIDE.md` - SMART Launch Universe setup
- `oracle_health_deployment_guide.md` - Oracle Health (Cerner) deployment
- `production_security_checklist.md` - Security verification before go-live

**Quality Controls:**
- **Deployment Checklist**: Step-by-step verification
- **Smoke Testing**: Post-deployment functionality checks
- **Security Hardening**: Production security configuration review
- **Backup and Recovery**: Verified backup procedures
- **Rollback Plan**: Documented rollback procedures in case of issues

---

#### Phase 7: Maintenance and Post-Market Surveillance
**Inputs:**
- Production software
- User feedback and complaints
- Security vulnerability reports
- Audit logs

**Activities:**
- **Issue Tracking and Resolution**: Bug fixes and enhancements
- **Security Patching**: Addressing vulnerabilities
- **Compliance Monitoring**: Ongoing ONC criteria compliance
- **Performance Monitoring**: System health and uptime tracking
- **User Support**: Responding to user questions and issues
- **Complaint Management**: Processing and reporting complaints to ONC

**Outputs:**
- Software updates and patches
- Issue resolution documentation
- Quarterly ONC complaint reports
- Audit reports
- Performance metrics

**Maintenance Documentation:**
- `COMPLAINT_PROCESS_DOCUMENTATION.md` - Complaint handling procedures
- `complaint_manager.py` - Complaint tracking tool
- `audit_viewer.py` - Audit log analysis tool

**Quality Controls:**
- **Change Control**: Formal approval process for all changes
- **Regression Testing**: Full test suite execution before each release
- **Security Updates**: Regular dependency updates and security patches
- **Audit Review**: Regular review of audit logs for security events
- **Complaint Analysis**: Quarterly analysis of trends and recurring issues

---

## 4. Quality Control Processes

### 4.1 Requirements Management

**Process:**
1. Requirements are documented in `software_requirements_specification.md`
2. Each requirement has a unique identifier (REQ-xxx)
3. Requirements are reviewed and approved by stakeholders
4. Changes to requirements trigger impact analysis and regression testing

**Traceability:**
- Requirements → Design → Code → Tests → Validation
- Traceability matrix maintained in requirements documentation

**Quality Metrics:**
- Requirements completeness: 100% of features have documented requirements
- Requirements stability: Track changes over time
- Test coverage: % of requirements with associated tests

---

### 4.2 Design Control

**Design Review Process:**
1. Design specifications created for major features
2. Peer review of design documents
3. Security and privacy impact assessment
4. Design approval before implementation begins

**Design Verification:**
- Design walkthroughs with development team
- Prototype demonstrations to stakeholders
- Usability heuristic evaluations

---

### 4.3 Code Quality Management

**Coding Standards:**
- **Python**: PEP 8 style guide
- **JavaScript**: ESLint with Airbnb style guide
- **HTML/CSS**: W3C standards and accessibility guidelines

**Code Review Process:**
1. All code changes go through pull request review
2. At least one peer reviewer approves changes
3. Automated checks must pass (linting, security scan, tests)
4. Code comments and documentation required for complex logic

**Automated Quality Checks:**
```bash
# Static analysis
pylint app.py fhir_data_service.py

# Security scanning
bandit -r . -f json -o security_report.json

# Dependency vulnerabilities
pip-audit
```

---

### 4.4 Configuration Management

**Version Control:**
- **Tool**: Git with GitHub
- **Branching Strategy**: 
  - `main` - Production-ready code
  - `develop` - Integration branch
  - `feature/*` - Feature development branches
  - `hotfix/*` - Emergency fixes

**Version Numbering:**
- Semantic versioning: `MAJOR.MINOR.PATCH`
- Major: Breaking changes or significant new features
- Minor: New features, backward compatible
- Patch: Bug fixes and small improvements

**Release Tagging:**
```bash
git tag -a v1.0.0 -m "Initial ONC-compliant release"
```

**Dependency Management:**
- All dependencies listed in `requirements.txt` with exact versions
- Regular security audits of dependencies
- Documented update procedures

---

### 4.5 Change Management

**Change Control Process:**
1. **Change Request**: Document proposed change with justification
2. **Impact Analysis**: Assess impact on functionality, security, compliance
3. **Risk Assessment**: Evaluate potential risks
4. **Approval**: Stakeholder approval for significant changes
5. **Implementation**: Develop and test changes
6. **Verification**: Ensure change meets requirements
7. **Documentation**: Update all relevant documentation
8. **Deployment**: Roll out to production with monitoring

**Change Classification:**
- **Critical**: Security vulnerabilities, patient safety issues - Immediate fix
- **High**: Major bugs, compliance issues - Fix within 1 week
- **Medium**: Minor bugs, usability improvements - Fix within 1 month
- **Low**: Enhancements, nice-to-have features - Scheduled for future release

---

### 4.6 Problem Resolution (Bug Management)

**Issue Tracking:**
- **Tool**: GitHub Issues (or equivalent)
- **Issue Categories**: Bug, Enhancement, Security, Compliance, Documentation
- **Priority Levels**: Critical, High, Medium, Low

**Bug Lifecycle:**
1. **Reported**: Issue identified and documented
2. **Triaged**: Severity and priority assigned
3. **Assigned**: Developer assigned to resolve
4. **In Progress**: Work underway
5. **Fixed**: Solution implemented
6. **Verified**: QA team verifies fix
7. **Closed**: Issue resolution confirmed

**Root Cause Analysis:**
- For critical and high-priority bugs, perform root cause analysis
- Document findings and preventive actions
- Update processes to prevent recurrence

---

## 5. Risk Management Integration

The QMS incorporates comprehensive risk management:

**Risk Management Documents:**
- `software_risk_analysis.md` - Systematic hazard analysis
- `risk_management_plan.md` - Risk mitigation strategies
- `risk_analysis_report.md` - HIPAA security risk assessment

**Risk Management Activities:**
- **Risk Identification**: Continuous throughout all lifecycle phases
- **Risk Analysis**: Severity and likelihood assessment
- **Risk Evaluation**: Determine acceptable vs. unacceptable risks
- **Risk Control**: Implement mitigation measures
- **Residual Risk Evaluation**: Verify risks reduced to acceptable levels
- **Risk Review**: Ongoing monitoring and periodic re-assessment

**Safety and Security:**
- Medical device risk analysis per ISO 14971
- HIPAA Security Rule compliance per 45 CFR 164.308
- ONC security criteria compliance

---

## 6. Measurement and Monitoring

### 6.1 Quality Metrics

**Process Metrics:**
- **Code Review Coverage**: % of code changes reviewed
- **Test Coverage**: % of code covered by automated tests
- **Build Success Rate**: % of successful CI/CD builds
- **Deployment Frequency**: Number of releases per time period

**Product Metrics:**
- **Defect Density**: Number of bugs per 1000 lines of code
- **Mean Time to Resolution (MTTR)**: Average time to fix bugs
- **System Uptime**: % availability
- **Response Time**: API endpoint performance

**Compliance Metrics:**
- **ONC Criteria Coverage**: Number of criteria fully met
- **Audit Log Completeness**: % of required events logged
- **Security Vulnerability Age**: Time from discovery to resolution

### 6.2 Quality Goals

**Current Status (as of October 2, 2025):**
- ✅ ONC Compliance: 10/17 criteria (59%)
- ✅ HIPAA Risk Mitigation: 6/7 risks mitigated
- ✅ Test Coverage: Comprehensive test suite with unit, integration, and system tests
- ✅ Security Scanning: Clean `bandit` and `pip-audit` reports
- ✅ Code Review: 100% of code changes reviewed

**Quality Targets:**
- **ONC Compliance**: Achieve 13/17 (76%) by Q4 2025
- **Test Coverage**: Maintain >80% code coverage
- **Security**: Zero critical vulnerabilities in production
- **Performance**: <2 second page load time for risk calculations
- **Uptime**: >99% availability

---

## 7. Documentation and Records

### 7.1 Required Documentation

**Product Documentation:**
- Software Requirements Specification
- Software Design Specifications
- Risk Management File
- Test Documentation
- User Documentation
- Deployment Guides

**Quality Records:**
- Design Review Records
- Code Review Records
- Test Reports and Results
- Validation Reports
- Issue Tracking Records
- Change Control Records
- Audit Logs
- Complaint Records

### 7.2 Document Control

**Version Control:**
- All documents maintained in version control (Git)
- Each document has version number and date
- Change history tracked in Git commits

**Review and Approval:**
- Critical documents reviewed by qualified personnel
- Approval documented in document header or Git commit message
- Periodic review schedule for all controlled documents

---

## 8. Training and Competence

### 8.1 Developer Competencies

**Required Skills:**
- Python programming (Flask framework)
- Web development (HTML, CSS, JavaScript)
- FHIR standards and healthcare interoperability
- Security best practices (HIPAA, OWASP)
- Software testing methodologies

**Training:**
- SMART on FHIR developer training
- Security awareness training
- Agile development methodologies
- Medical device software development (IEC 62304)

### 8.2 Quality Awareness

All team members are trained on:
- Quality objectives and policies
- Their role in the QMS
- Consequences of non-conformance
- Reporting quality issues and complaints

---

## 9. Continuous Improvement

### 9.1 Improvement Process

**Sources of Improvement Opportunities:**
- User feedback and complaints
- Audit findings
- Test results and metrics
- Security vulnerability reports
- Regulatory changes
- Technology advancements

**Improvement Cycle (PDCA):**
1. **Plan**: Identify improvement opportunity and create action plan
2. **Do**: Implement the improvement on a trial basis
3. **Check**: Measure and evaluate results
4. **Act**: Standardize if successful, or revise if not

### 9.2 Management Review

**Periodic Reviews:**
- **Quarterly**: Review quality metrics, complaints, audit findings
- **Annually**: Comprehensive QMS effectiveness review
- **Post-Release**: Review after each major release

**Review Outputs:**
- Action items for improvement
- Resource allocation decisions
- Updates to QMS processes

---

## 10. Compliance Mapping

### 10.1 ONC Certification Criteria

**45 CFR 170.315 (g)(4) - Quality Management System**

This QMS documentation satisfies the requirement by:

✅ **Identifying the QMS**: ISO 9001:2015-based approach is identified  
✅ **Development**: SDLC phases and processes documented  
✅ **Testing**: Comprehensive testing strategy described  
✅ **Implementation**: Deployment and release processes defined  
✅ **Maintenance**: Ongoing support and improvement processes established

### 10.2 Other Standards

**ISO 9001:2015 Alignment:**
- Context of the organization (Section 2)
- Leadership and quality policy (Section 2.1)
- Planning and risk management (Section 5)
- Support and resources (Section 8)
- Operation (Sections 3-7)
- Performance evaluation (Section 6)
- Improvement (Section 9)

**IEC 62304 Medical Device Software:**
- Software development planning (Section 3)
- Software requirements analysis (Phase 1)
- Software architectural design (Phase 2)
- Software detailed design and implementation (Phase 3)
- Software verification and validation (Phases 4-5)
- Software maintenance (Phase 7)

---

## 11. Revision History

| Version | Date | Author | Changes |
|:---|:---|:---|:---|
| 1.0 | 2025-10-02 | Development Team | Initial QMS documentation for ONC compliance |

---

## 12. Appendices

### Appendix A: Related Documents

- `software_requirements_specification.md` - Functional and non-functional requirements
- `software_risk_analysis.md` - ISO 14971 risk analysis
- `risk_management_plan.md` - Risk mitigation strategies
- `TEST_REPORT.md` - Comprehensive testing results
- `TESTING_METHODOLOGY.md` - Testing approach and tools
- `DEPLOYMENT_GUIDE.md` - Production deployment procedures
- `COMPLAINT_PROCESS_DOCUMENTATION.md` - Complaint handling procedures
- `onc_certification_compliance_assessment.md` - ONC criteria compliance status

### Appendix B: Quality Tools and Technologies

**Development Tools:**
- Python 3.8+, Flask 2.2+
- Git / GitHub
- Visual Studio Code / PyCharm

**Testing Tools:**
- pytest - Unit and integration testing
- locust - Performance testing
- pytest-cov - Code coverage

**Quality Tools:**
- pylint, flake8 - Static code analysis
- bandit - Security vulnerability scanning
- pip-audit - Dependency vulnerability checking

**Deployment Tools:**
- Docker - Containerization
- Gunicorn - WSGI server
- Cloud platforms - Google App Engine, Render, etc.

### Appendix C: Key Quality Roles

| Role | Responsibilities |
|:---|:---|
| **Project Lead** | Overall quality accountability, QMS oversight |
| **Developer** | Code quality, unit testing, documentation |
| **QA Engineer** | Test planning, test execution, defect tracking |
| **Security Specialist** | Security architecture, vulnerability management |
| **Clinical Advisor** | Requirements validation, clinical accuracy verification |
| **Compliance Officer** | Regulatory compliance, ONC certification |

---

**Document Owner:** Project Lead  
**Review Frequency:** Annually or upon significant process changes  
**Next Review Date:** October 2026

---

**This Quality Management System documentation demonstrates compliance with 45 CFR 170.315 (g)(4) by clearly identifying the QMS framework and processes used throughout the software lifecycle.**

