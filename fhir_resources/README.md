# FHIR Resources

This directory contains FHIR-related resources for the PRECISE-HBR application.

## 📁 Directory Structure

### `/valuesets`
FHIR ValueSet definitions and terminology resources

Contains ValueSets for:
- Bleeding risk criteria
- Clinical conditions (bleeding diathesis, cancer, stroke, etc.)
- Laboratory values
- Medications
- Procedures

## 📋 ValueSet Files

ValueSet files follow FHIR R4 format and include:

### Major Criteria ValueSets
- Previous bleeding events
- Anemia (hemoglobin levels)
- Chronic kidney disease (eGFR)
- Thrombocytopenia
- Liver disease with portal hypertension

### Minor Criteria ValueSets
- Age criteria
- Medication interactions
- Comorbidities
- Recent procedures

## 🔧 Usage

These ValueSets are used by the application to:
1. Query FHIR servers for relevant patient data
2. Evaluate PRECISE-HBR criteria
3. Generate clinical decision support recommendations
4. Create CCD exports

## 📚 FHIR Specifications

- **FHIR Version:** R4
- **Format:** JSON
- **Terminology:** SNOMED CT, LOINC, RxNorm

## 🔄 Updating ValueSets

When updating ValueSets:
1. Ensure compliance with FHIR R4 specification
2. Validate JSON structure
3. Test with FHIR server queries
4. Update application code if needed
5. Document changes in version control

## 📖 References

- [FHIR ValueSet Resource](http://hl7.org/fhir/valueset.html)
- [PRECISE-HBR Criteria](../PRECISE-HBR.md)
- [SNOMED CT](https://www.snomed.org/)
- [LOINC](https://loinc.org/)

---

**Last Updated:** October 2025

