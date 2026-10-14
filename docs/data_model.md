
# ICT Governance Platform — Data Model

## Purpose

This document defines the initial logical data model for the
AI-Powered ICT Governance & Risk Automation Platform.

All Phase 1 records are synthetic demonstration data.

## 1. Assets

Primary key: `asset_id`

Stores information about technology assets and business services.

Important fields:
- `asset_id`: unique asset identifier
- `asset_name`: display name
- `asset_type`: type of technology asset
- `business_service`: associated business service
- `environment`: Production, Pre-Production, or Development
- `criticality`: business criticality
- `owner`: accountable demonstration team
- `internet_exposed`: whether the asset is internet-facing
- `data_classification`: classification of information handled
- `created_date`: date the synthetic record was created

## 2. ICT Controls

Primary key: `control_id`

Stores control requirements and their assessed effectiveness.

Important fields:
- `control_id`: unique control identifier
- `control_name`: control display name
- `control_domain`: governance or security domain
- `requirement`: expected control behaviour
- `control_owner`: responsible demonstration team
- `frequency`: intended review frequency
- `effectiveness_status`: assessment result
- `last_tested_date`: last test date

## 3. Security Findings

Primary key: `finding_id`

Foreign keys:
- `asset_id` references Assets.asset_id
- `control_id` references ICT_Controls.control_id

Stores security findings associated with technology assets and controls.

Important fields:
- `finding_id`: unique finding identifier
- `title`: short finding title
- `finding_type`: category of issue
- `severity`: Critical, High, Medium, or Low
- `cvss_score`: synthetic score from 0 to 10
- `discovered_date`: discovery date
- `due_date`: remediation target date
- `status`: current finding status
- `source`: synthetic detection or assessment source
- `description`: demonstration-only description

## 4. Remediation Actions

Primary key: `action_id`

Foreign key:
- `finding_id` references Security_Findings.finding_id

Stores the work required to address a finding.

Important fields:
- `action_id`: unique action identifier
- `finding_id`: associated security finding
- `assigned_to`: responsible demonstration team
- `action_title`: task description
- `priority`: priority derived from finding severity
- `status`: Planned, In Progress, Blocked, or Completed
- `created_date`: action creation date
- `due_date`: target date
- `completed_date`: completion date, when completed
- `evidence_reference`: synthetic evidence identifier
- `comments`: demonstration notes

## Relationships

- One Asset can have many Security Findings.
- One ICT Control can be linked to many Security Findings.
- One Security Finding can have many Remediation Actions.

## Data quality requirements

- Every primary key must be unique and non-empty.
- Every foreign key must reference an existing record.
- CVSS scores must be between 0 and 10.
- Due dates must not precede discovery dates.
- Completed remediation actions must have a completion date.
- Non-completed remediation actions must not have a completion date.

## Design note

This is a logical data model for a demonstration project.
Dataverse implementation may use platform-generated GUIDs as
physical primary keys, with these IDs retained as alternate keys
or external business identifiers where appropriate.
