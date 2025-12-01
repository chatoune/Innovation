# Data Model: Client/Server Application Platform

**Branch**: `001-architecture-docs` | **Date**: 2025-12-01

## Entity Relationship Diagram

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│    User     │       │    Role     │       │ Permission  │
├─────────────┤       ├─────────────┤       ├─────────────┤
│ id (PK)     │       │ id (PK)     │       │ id (PK)     │
│ email       │       │ name        │       │ code        │
│ password_h  │──────<│ description │>──────│ description │
│ is_active   │       │ created_at  │       │ resource    │
│ created_at  │       │ updated_at  │       │ action      │
│ updated_at  │       └─────────────┘       └─────────────┘
│ locked_until│              │                    │
│ failed_att  │              │                    │
└─────────────┘              │                    │
      │                      │                    │
      │    ┌─────────────────┴────────┐          │
      │    │       user_roles         │          │
      │    ├──────────────────────────┤          │
      └───<│ user_id (FK)             │          │
           │ role_id (FK)             │          │
           │ assigned_at              │          │
           └──────────────────────────┘          │
                                                 │
           ┌──────────────────────────┐          │
           │    role_permissions      │          │
           ├──────────────────────────┤          │
           │ role_id (FK)             │>─────────┘
           │ permission_id (FK)       │
           └──────────────────────────┘

┌─────────────┐       ┌─────────────┐
│   Module    │       │  AuditLog   │
├─────────────┤       ├─────────────┤
│ id (PK)     │       │ id (PK)     │
│ code        │       │ timestamp   │
│ label       │       │ user_id(FK) │
│ route       │       │ action      │
│ icon        │       │ resource_t  │
│ sort_order  │       │ resource_id │
│ is_active   │       │ details     │
│ parent_id   │       │ ip_address  │
└─────────────┘       └─────────────┘
      │
      │    ┌──────────────────────────┐
      │    │   module_permissions     │
      │    ├──────────────────────────┤
      └───<│ module_id (FK)           │
           │ permission_id (FK)       │
           └──────────────────────────┘

┌─────────────────────┐       ┌─────────────────────┐
│   FIDO2Credential   │       │    ImportJob        │
├─────────────────────┤       ├─────────────────────┤
│ id (PK)             │       │ id (PK)             │
│ user_id (FK)        │       │ user_id (FK)        │
│ credential_id       │       │ filename            │
│ public_key          │       │ status              │
│ sign_count          │       │ total_rows          │
│ device_name         │       │ processed_rows      │
│ created_at          │       │ error_count         │
│ last_used_at        │       │ errors (JSONB)      │
└─────────────────────┘       │ created_at          │
                              │ completed_at        │
                              └─────────────────────┘
```

## Entity Definitions

### User

Represents a person who can authenticate and interact with the system.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| email | VARCHAR(255) | UNIQUE, NOT NULL | Login identifier |
| password_hash | VARCHAR(255) | NULL | Argon2id hash (null for FIDO2-only users) |
| is_active | BOOLEAN | DEFAULT true | Account status |
| created_at | TIMESTAMP | NOT NULL | Account creation time |
| updated_at | TIMESTAMP | NOT NULL | Last modification time |
| locked_until | TIMESTAMP | NULL | Account lockout expiry (null = not locked) |
| failed_attempts | INTEGER | DEFAULT 0 | Failed login counter (resets on success) |

**Validation Rules**:
- Email must be valid email format
- Email uniqueness enforced at database level
- Account locks after 5 consecutive failed attempts
- Locked accounts cannot authenticate until `locked_until` expires

**State Transitions**:
- `active` → `inactive`: Admin deactivates account
- `inactive` → `active`: Admin reactivates account
- `active` → `locked`: 5 failed login attempts
- `locked` → `active`: Lockout period expires or admin unlocks

### Role

A named collection of permissions that can be assigned to users.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| name | VARCHAR(100) | UNIQUE, NOT NULL | Role display name |
| description | TEXT | NULL | Role purpose description |
| created_at | TIMESTAMP | NOT NULL | Creation time |
| updated_at | TIMESTAMP | NOT NULL | Last modification time |

**Validation Rules**:
- Name must be unique (case-insensitive comparison)
- Name cannot be empty
- Deleting a role cascades to remove all user_roles assignments

**Seeded Data**:
- `Administrator`: Full system access
- `User Manager`: Can manage users and roles
- `Importer`: Can import Excel files
- `Viewer`: Read-only access

### Permission

A specific capability or access right.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| code | VARCHAR(100) | UNIQUE, NOT NULL | Machine-readable identifier |
| description | VARCHAR(255) | NOT NULL | Human-readable description |
| resource | VARCHAR(50) | NOT NULL | Resource category (users, roles, import, etc.) |
| action | VARCHAR(50) | NOT NULL | Action type (read, write, delete, manage) |

**Permission Code Pattern**: `{resource}:{action}`

**Seeded Permissions**:
| Code | Description | Resource | Action |
|------|-------------|----------|--------|
| users:read | View user list and details | users | read |
| users:write | Create and update users | users | write |
| users:delete | Deactivate users | users | delete |
| roles:read | View roles and permissions | roles | read |
| roles:manage | Create, update, delete roles | roles | manage |
| import:execute | Upload and import Excel files | import | execute |
| audit:read | View audit logs | audit | read |
| modules:manage | Configure navigation modules | modules | manage |

### Module

A navigable section of the application.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| code | VARCHAR(50) | UNIQUE, NOT NULL | Machine-readable identifier |
| label | VARCHAR(100) | NOT NULL | Display name in sidebar |
| route | VARCHAR(255) | NOT NULL | Frontend route path |
| icon | VARCHAR(50) | NULL | Icon identifier |
| sort_order | INTEGER | DEFAULT 0 | Display order in sidebar |
| is_active | BOOLEAN | DEFAULT true | Visibility toggle |
| parent_id | UUID | FK (self) | Parent module for nested navigation |

**Seeded Modules**:
| Code | Label | Route | Required Permission |
|------|-------|-------|---------------------|
| dashboard | Dashboard | /dashboard | (none - visible to all) |
| users | Users | /users | users:read |
| roles | Roles | /roles | roles:read |
| import | Excel Import | /import | import:execute |
| audit | Audit Log | /audit | audit:read |

### FIDO2Credential

Stored public key for hardware security key authentication.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| user_id | UUID | FK (User), NOT NULL | Owner of credential |
| credential_id | BYTEA | UNIQUE, NOT NULL | WebAuthn credential ID |
| public_key | BYTEA | NOT NULL | COSE public key |
| sign_count | INTEGER | NOT NULL | Signature counter for clone detection |
| device_name | VARCHAR(100) | NULL | User-provided device label |
| created_at | TIMESTAMP | NOT NULL | Registration time |
| last_used_at | TIMESTAMP | NULL | Last successful authentication |

**Validation Rules**:
- credential_id must be unique across all users
- sign_count must increase on each authentication (replay protection)
- User may have multiple credentials (backup keys)

### AuditLog

Immutable record of significant system events.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| timestamp | TIMESTAMP | NOT NULL, INDEX | Event time (UTC) |
| user_id | UUID | FK (User), NULL | Acting user (null for system events) |
| action | VARCHAR(50) | NOT NULL, INDEX | Event type |
| resource_type | VARCHAR(50) | NOT NULL | Affected entity type |
| resource_id | VARCHAR(255) | NULL | Affected entity ID |
| details | JSONB | NULL | Additional context (before/after values) |
| ip_address | VARCHAR(45) | NULL | Client IP address |

**Action Types**:
- `LOGIN_SUCCESS`, `LOGIN_FAILURE`, `LOGOUT`
- `USER_CREATE`, `USER_UPDATE`, `USER_DEACTIVATE`, `USER_REACTIVATE`
- `ROLE_CREATE`, `ROLE_UPDATE`, `ROLE_DELETE`
- `PERMISSION_DENIED`
- `IMPORT_START`, `IMPORT_SUCCESS`, `IMPORT_FAILURE`
- `FIDO2_REGISTER`, `FIDO2_REMOVE`

**Constraints**:
- No UPDATE or DELETE allowed on this table
- Indexes on timestamp, user_id, action for query performance

### ImportJob

Tracks Excel import operations and their progress.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| user_id | UUID | FK (User), NOT NULL | User who initiated import |
| filename | VARCHAR(255) | NOT NULL | Original filename |
| status | VARCHAR(20) | NOT NULL | Job status |
| total_rows | INTEGER | NULL | Total data rows in file |
| processed_rows | INTEGER | DEFAULT 0 | Rows processed so far |
| error_count | INTEGER | DEFAULT 0 | Rows with errors |
| errors | JSONB | NULL | Array of {row, column, message} |
| created_at | TIMESTAMP | NOT NULL | Upload time |
| completed_at | TIMESTAMP | NULL | Processing completion time |

**Status Values**:
- `queued`: Waiting to be processed
- `processing`: Currently being processed
- `completed`: Successfully imported all rows
- `failed`: Critical error, import rolled back
- `completed_with_errors`: Partial success (if allowed by import type)

## Junction Tables

### user_roles

| Field | Type | Constraints |
|-------|------|-------------|
| user_id | UUID | PK, FK (User) |
| role_id | UUID | PK, FK (Role) |
| assigned_at | TIMESTAMP | NOT NULL |

**Cascade Behavior**: Deleting a Role removes all user_roles entries for that role.

### role_permissions

| Field | Type | Constraints |
|-------|------|-------------|
| role_id | UUID | PK, FK (Role) |
| permission_id | UUID | PK, FK (Permission) |

**Cascade Behavior**: Deleting a Role removes all role_permissions entries.

### module_permissions

| Field | Type | Constraints |
|-------|------|-------------|
| module_id | UUID | PK, FK (Module) |
| permission_id | UUID | PK, FK (Permission) |

**Behavior**: User sees module if they have ANY of the required permissions.

## Indexes

```sql
-- User lookups
CREATE UNIQUE INDEX idx_users_email ON users(LOWER(email));

-- Role lookups
CREATE UNIQUE INDEX idx_roles_name ON roles(LOWER(name));

-- Permission lookups
CREATE UNIQUE INDEX idx_permissions_code ON permissions(code);

-- Audit log queries
CREATE INDEX idx_audit_timestamp ON audit_log(timestamp DESC);
CREATE INDEX idx_audit_user ON audit_log(user_id, timestamp DESC);
CREATE INDEX idx_audit_action ON audit_log(action, timestamp DESC);

-- FIDO2 credential lookup
CREATE UNIQUE INDEX idx_fido2_credential_id ON fido2_credentials(credential_id);

-- Import job queries
CREATE INDEX idx_import_user_status ON import_jobs(user_id, status);
```
