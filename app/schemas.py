from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=256)
    mfa_code: str | None = Field(default=None, min_length=6, max_length=6)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=8, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)
    confirm_password: str = Field(min_length=8, max_length=256)


class MfaCode(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class SystemSettingsUpdate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    display_name: str = Field(min_length=1, max_length=128)
    current_password: str = Field(min_length=8, max_length=256)
    new_password: str | None = Field(default=None, min_length=8, max_length=256)
    confirm_password: str | None = Field(default=None, max_length=256)

    @field_validator("username", "display_name", "current_password", "new_password", "confirm_password", mode="before")
    @classmethod
    def trim_settings_text(cls, value: Any) -> str | None:
        if value is None:
            return None
        value = str(value).strip()
        return value or None


class AdministratorCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    display_name: str = Field(min_length=1, max_length=128)
    role: str = Field(default="admin", pattern="^(admin|teacher)$")
    permissions: list[str] | None = Field(default=None, max_length=20)
    password: str = Field(min_length=8, max_length=256)
    confirm_password: str = Field(min_length=8, max_length=256)
    current_password: str = Field(min_length=8, max_length=256)

    @field_validator("username", "display_name", "password", "confirm_password", "current_password", mode="before")
    @classmethod
    def trim_administrator_text(cls, value: Any) -> str:
        value = str(value).strip() if value is not None else ""
        if not value:
            raise ValueError("不能为空")
        return value


class AdministratorUpdate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    display_name: str = Field(min_length=1, max_length=128)
    role: str = Field(default="admin", pattern="^(admin|teacher)$")
    permissions: list[str] | None = Field(default=None, max_length=20)
    current_password: str = Field(min_length=8, max_length=256)
    new_password: str | None = Field(default=None, min_length=8, max_length=256)
    confirm_password: str | None = Field(default=None, max_length=256)

    @field_validator("username", "display_name", "current_password", "new_password", "confirm_password", mode="before")
    @classmethod
    def trim_administrator_text(cls, value: Any) -> str | None:
        if value is None:
            return None
        value = str(value).strip()
        return value or None


class StudentInput(BaseModel):
    student_no: str = Field(min_length=1, max_length=64)
    candidate_no: str | None = Field(default=None, max_length=64)
    full_name: str = Field(min_length=1, max_length=128)
    gender: str | None = Field(default=None, max_length=16)
    national_id: str | None = Field(default=None, max_length=32)
    date_of_birth: date | None = None
    student_origin: str | None = Field(default=None, max_length=255)
    ethnicity: str | None = Field(default=None, max_length=64)
    political_status: str | None = Field(default=None, max_length=64)
    enrollment_date: date | None = None
    graduation_year: str | None = Field(default=None, max_length=16)
    graduation_date: date | None = None
    urban_rural_origin: str | None = Field(default=None, max_length=32)
    pre_enrollment_archive_unit: str | None = Field(default=None, max_length=255)
    archive_transferred: str | None = Field(default=None, max_length=16)
    pre_enrollment_police_station: str | None = Field(default=None, max_length=255)
    household_registration_transferred: str | None = Field(default=None, max_length=16)
    education_level: str | None = Field(default=None, max_length=64)
    program_duration: str | None = Field(default=None, max_length=32)
    school: str | None = Field(default=None, max_length=128)
    college: str | None = Field(default=None, max_length=128)
    school_major: str | None = Field(default=None, max_length=128)
    major_direction: str | None = Field(default=None, max_length=128)
    current_class: str | None = Field(default=None, max_length=64)
    training_mode: str | None = Field(default=None, max_length=64)
    commissioned_unit: str | None = Field(default=None, max_length=255)
    hardship_category: str | None = Field(default=None, max_length=64)
    normal_student_category: str | None = Field(default=None, max_length=64)
    mobile_phone: str | None = Field(default=None, max_length=32)
    electronic_email: str | None = Field(default=None, max_length=255)
    qq_number: str | None = Field(default=None, max_length=32)
    family_phone: str | None = Field(default=None, max_length=32)
    family_postcode: str | None = Field(default=None, max_length=16)
    family_address: str | None = Field(default=None, max_length=500)
    poverty_county_52: str | None = Field(default=None, max_length=16)
    poverty_county_province: str | None = Field(default=None, max_length=64)
    poverty_county_city: str | None = Field(default=None, max_length=64)
    poverty_county_district: str | None = Field(default=None, max_length=64)
    registered_poor: str | None = Field(default=None, max_length=16)
    study_mode: str | None = Field(default=None, max_length=64)
    vocational_expansion_flag: str | None = Field(default=None, max_length=16)
    remarks: str | None = Field(default=None, max_length=2000)

    @field_validator("student_no", "full_name", mode="before")
    @classmethod
    def trim_required_text(cls, value: Any) -> str:
        value = str(value).strip() if value is not None else ""
        if not value:
            raise ValueError("不能为空")
        return value

    @field_validator(
        "candidate_no", "gender", "national_id", "student_origin", "ethnicity", "political_status", "graduation_year",
        "urban_rural_origin", "pre_enrollment_archive_unit", "archive_transferred", "pre_enrollment_police_station",
        "household_registration_transferred", "education_level", "program_duration", "school", "college", "school_major",
        "major_direction", "current_class", "training_mode", "commissioned_unit", "hardship_category", "normal_student_category",
        "mobile_phone", "electronic_email", "qq_number", "family_phone", "family_postcode", "family_address", "poverty_county_52",
        "poverty_county_province", "poverty_county_city", "poverty_county_district", "registered_poor", "study_mode",
        "vocational_expansion_flag", "remarks", mode="before"
    )
    @classmethod
    def trim_optional_text(cls, value: Any) -> str | None:
        if value is None:
            return None
        value = str(value).strip()
        return value or None


class StudentCreate(StudentInput):
    pass


class StudentUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=128)
    candidate_no: str | None = Field(default=None, max_length=64)
    gender: str | None = Field(default=None, max_length=16)
    national_id: str | None = Field(default=None, max_length=32)
    date_of_birth: date | None = None
    student_origin: str | None = Field(default=None, max_length=255)
    ethnicity: str | None = Field(default=None, max_length=64)
    political_status: str | None = Field(default=None, max_length=64)
    enrollment_date: date | None = None
    graduation_year: str | None = Field(default=None, max_length=16)
    graduation_date: date | None = None
    urban_rural_origin: str | None = Field(default=None, max_length=32)
    pre_enrollment_archive_unit: str | None = Field(default=None, max_length=255)
    archive_transferred: str | None = Field(default=None, max_length=16)
    pre_enrollment_police_station: str | None = Field(default=None, max_length=255)
    household_registration_transferred: str | None = Field(default=None, max_length=16)
    education_level: str | None = Field(default=None, max_length=64)
    program_duration: str | None = Field(default=None, max_length=32)
    school: str | None = Field(default=None, max_length=128)
    college: str | None = Field(default=None, max_length=128)
    school_major: str | None = Field(default=None, max_length=128)
    major_direction: str | None = Field(default=None, max_length=128)
    current_class: str | None = Field(default=None, max_length=64)
    training_mode: str | None = Field(default=None, max_length=64)
    commissioned_unit: str | None = Field(default=None, max_length=255)
    hardship_category: str | None = Field(default=None, max_length=64)
    normal_student_category: str | None = Field(default=None, max_length=64)
    mobile_phone: str | None = Field(default=None, max_length=32)
    electronic_email: str | None = Field(default=None, max_length=255)
    qq_number: str | None = Field(default=None, max_length=32)
    family_phone: str | None = Field(default=None, max_length=32)
    family_postcode: str | None = Field(default=None, max_length=16)
    family_address: str | None = Field(default=None, max_length=500)
    poverty_county_52: str | None = Field(default=None, max_length=16)
    poverty_county_province: str | None = Field(default=None, max_length=64)
    poverty_county_city: str | None = Field(default=None, max_length=64)
    poverty_county_district: str | None = Field(default=None, max_length=64)
    registered_poor: str | None = Field(default=None, max_length=16)
    study_mode: str | None = Field(default=None, max_length=64)
    vocational_expansion_flag: str | None = Field(default=None, max_length=16)
    remarks: str | None = Field(default=None, max_length=2000)
    row_version: int = Field(ge=1)


class StudentResponse(StudentInput):
    model_config = ConfigDict(from_attributes=True)

    id: int
    row_version: int
    created_at: datetime
    updated_at: datetime


class AiQuestion(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    conversation_id: UUID | None = None


class ExcelImportCommit(BaseModel):
    preview_id: UUID
    mode: str = Field(pattern="^(upsert|create_only|update_only)$")
    mapping: dict[str, str | None] = Field(default_factory=dict)
    required_fields: list[str] = Field(default_factory=list)
    update_policy: str = Field(default="overwrite", pattern="^(overwrite|only_blank)$")
    background_task: bool = False


class ImportTemplateInput(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    mapping: dict[str, str | None] = Field(default_factory=dict)
    required_fields: list[str] = Field(default_factory=list)
    default_mode: str = Field(default="upsert", pattern="^(upsert|create_only|update_only)$")
    update_policy: str = Field(default="overwrite", pattern="^(overwrite|only_blank)$")


class ExportTemplateInput(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    fields: list[str] = Field(default_factory=list, max_length=48)
    filters: dict[str, str] = Field(default_factory=dict)
    include_provenance: bool = True
    mask_sensitive: bool = False


class DataScopeRuleInput(BaseModel):
    school: str | None = Field(default=None, max_length=128)
    college: str | None = Field(default=None, max_length=128)
    school_major: str | None = Field(default=None, max_length=128)
    current_class: str | None = Field(default=None, max_length=64)


class DataScopeUpdate(DataScopeRuleInput):
    rules: list[DataScopeRuleInput] = Field(default_factory=list, max_length=30)


class SystemControlsUpdate(BaseModel):
    ai_operations_enabled: bool = True
    ai_export_confirmation_required: bool = True


class StudentDeletion(BaseModel):
    student_no: str = Field(min_length=1, max_length=64)
    confirmation_phrase: str = Field(min_length=1, max_length=16)

    @field_validator("student_no", "confirmation_phrase", mode="before")
    @classmethod
    def trim_confirmation(cls, value: Any) -> str:
        return str(value or "").strip()


class CandidateApproval(StudentInput):
    pass
