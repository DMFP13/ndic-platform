"""
Enumeration types for the Nigerian Dairy Intelligence Consortium (NDIC) platform.
All enums use string values for PostgreSQL ENUM compatibility and JSON serialisability.
"""

from enum import Enum


class UserRole(str, Enum):
    FARM = "farm"
    PROCESSOR = "processor"
    GOVERNMENT = "government"
    LENDER = "lender"
    ARPEXAS_ADMIN = "arpexas_admin"


class OrganizationType(str, Enum):
    FARM = "farm"
    PROCESSING_COMPANY = "processing_company"
    GOVERNMENT_AGENCY = "government_agency"
    FINANCE_INSTITUTION = "finance_institution"


class AnimalSex(str, Enum):
    MALE = "male"
    FEMALE = "female"


class AnimalStatus(str, Enum):
    ACTIVE = "active"
    DECEASED = "deceased"
    SOLD = "sold"
    TRANSFERRED = "transferred"
    QUARANTINED = "quarantined"


class AnimalBreed(str, Enum):
    # Indigenous Nigerian breeds
    BUNAJI = "bunaji"          # White Fulani — dominant dairy breed in Nigeria
    RAHAJI = "rahaji"          # Red Fulani
    AZAWAK = "azawak"          # Sahelian zebu
    SHUWA_ARAB = "shuwa_arab"  # Shuwa Arab cattle, NE Nigeria
    MUTURU = "muturu"          # West African Dwarf — trypanotolerant
    KETEKU = "keteku"          # Yoruba crossbreed
    # Exotic / improved breeds
    FRIESIAN = "friesian"      # Holstein Friesian
    JERSEY = "jersey"
    BROWN_SWISS = "brown_swiss"
    # Crosses
    FRIESIAN_BUNAJI_CROSS = "friesian_bunaji_cross"
    CROSSBREED = "crossbreed"
    OTHER = "other"


class DiseaseType(str, Enum):
    FOOT_AND_MOUTH = "foot_and_mouth"
    CBPP = "cbpp"                          # Contagious Bovine Pleuropneumonia
    BRUCELLOSIS = "brucellosis"
    LUMPY_SKIN_DISEASE = "lumpy_skin_disease"
    ANTHRAX = "anthrax"
    MASTITIS = "mastitis"
    TRYPANOSOMIASIS = "trypanosomiasis"
    BOVINE_TUBERCULOSIS = "bovine_tuberculosis"
    HAEMORRHAGIC_SEPTICAEMIA = "haemorrhagic_septicaemia"
    EAST_COAST_FEVER = "east_coast_fever"
    RIFT_VALLEY_FEVER = "rift_valley_fever"
    OTHER = "other"


class AlertConfirmationStatus(str, Enum):
    SUSPECTED = "suspected"
    CONFIRMED = "confirmed"
    RESOLVED = "resolved"
    FALSE_ALARM = "false_alarm"


class AlertSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class QualityGrade(str, Enum):
    A = "A"           # Premium: fat ≥3.5%, protein ≥3.2%, SCC <200k
    B = "B"           # Standard
    C = "C"           # Below standard — accepted at reduced price
    REJECTED = "rejected"


class CollateralConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class LedgerEventType(str, Enum):
    ANIMAL_REGISTERED = "animal_registered"
    ANIMAL_STATUS_CHANGED = "animal_status_changed"
    HEALTH_RECORD_SUBMITTED = "health_record_submitted"
    PROCESSOR_INTAKE_SUBMITTED = "processor_intake_submitted"
    DISEASE_ALERT_SUBMITTED = "disease_alert_submitted"
    DISEASE_ALERT_STATUS_UPDATED = "disease_alert_status_updated"
    LENDER_ASSESSMENT_SUBMITTED = "lender_assessment_submitted"
    USER_CREATED = "user_created"
    ORGANIZATION_REGISTERED = "organization_registered"
    FARM_REGISTERED = "farm_registered"
    ACCESS_GRANTED = "access_granted"
    ACCESS_REVOKED = "access_revoked"
