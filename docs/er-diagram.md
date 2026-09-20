# ER Diagram

Tables and their relationships.

## Relationships

```
users (1) ──────────────── (1) user_profiles
  │
  └── (1) ──────────────── (0..1) doctors
                                │
                                └── (1:N) availability_slots
                                               │
                                               └── (0..1) consultations
                                                              │
                                                              ├── (1:N) consultation_notes
                                                              ├── (0..1) prescriptions
                                                              │               └── (1:N) medications
                                                              └── (0..1) payments

users (1) ──── (1:N) audit_logs
```

## Table columns

**users**
- id: uuid (PK)
- email: varchar unique
- hashed_password: varchar
- role: enum (patient, doctor, admin)
- is_active: bool
- mfa_enabled: bool
- mfa_secret: varchar nullable
- created_at, updated_at: timestamptz

**user_profiles**
- id: uuid (PK)
- user_id: uuid (FK → users)
- first_name, last_name: varchar
- phone: varchar
- date_of_birth: date
- gender: enum
- address: text
- avatar_url: varchar

**doctors**
- id: uuid (PK)
- user_id: uuid (FK → users, unique)
- specialty: varchar
- license_number: varchar unique
- bio: text
- years_experience: int
- consultation_fee: numeric
- is_verified: bool
- rating: float (updated by Celery task)
- total_consultations: int

**availability_slots**
- id: uuid (PK)
- doctor_id: uuid (FK → doctors)
- start_time, end_time: timestamptz
- duration_minutes: int (default 30)
- is_booked: bool
- is_active: bool
- recurrence_rule: varchar nullable

**consultations**
- id: uuid (PK)
- patient_id: uuid (FK → users)
- doctor_id: uuid (FK → doctors)
- slot_id: uuid (FK → availability_slots, unique)
- status: enum (scheduled, in_progress, completed, cancelled)
- chief_complaint: text
- idempotency_key: varchar unique — prevents duplicate bookings on retry
- scheduled_at, started_at, ended_at: timestamptz

**consultation_notes**
- id: uuid (PK)
- consultation_id: uuid (FK → consultations)
- author_id: uuid (FK → users)
- content: text
- created_at: timestamptz

**prescriptions**
- id: uuid (PK)
- consultation_id: uuid (FK → consultations, unique)
- issued_by: uuid (FK → users / doctor)
- diagnosis: text
- instructions: text
- follow_up_date: timestamptz
- is_active: bool

**medications**
- id: uuid (PK)
- prescription_id: uuid (FK → prescriptions)
- name, dosage, frequency, route: varchar
- duration_days: int

**payments**
- id: uuid (PK)
- consultation_id: uuid (FK → consultations, unique)
- patient_id: uuid (FK → users)
- amount: numeric
- currency: varchar
- status: enum (pending, completed, failed, refunded)
- gateway_ref: varchar unique
- idempotency_key: varchar unique

**audit_logs**
- id: uuid (PK)
- user_id: uuid (FK → users, nullable)
- action: varchar
- resource_type, resource_id: varchar
- ip_address: varchar
- outcome: varchar
- extra: jsonb (no PHI)
- created_at: timestamptz
