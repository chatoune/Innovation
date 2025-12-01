# Tasks: Client/Server Application Platform

**Input**: Design documents from `/specs/001-architecture-docs/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml

**Tests**: Not explicitly requested in specification. Implementation tasks only.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- File paths use `backend/src/` and `frontend/src/` per plan.md web structure

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependencies, and basic structure

- [x] T001 Create backend directory structure per plan.md in backend/
- [x] T002 Create frontend directory structure per plan.md in frontend/
- [x] T003 [P] Initialize Python project with pyproject.toml in backend/
- [x] T004 [P] Initialize frontend project with package.json in frontend/
- [x] T005 [P] Create backend requirements.txt with FastAPI, SQLAlchemy, uvicorn, argon2-cffi, py_webauthn, python-jose, pandas, openpyxl
- [x] T006 [P] Create frontend dependencies with React, react-router-dom, axios, tailwindcss in frontend/package.json
- [x] T007 [P] Configure backend linting with ruff.toml in backend/
- [x] T008 [P] Configure frontend linting with eslint.config.js in frontend/
- [x] T009 [P] Create backend .env.example with DATABASE_URL, SECRET_KEY, CORS_ORIGINS in backend/
- [x] T010 [P] Create frontend .env.example with VITE_API_URL in frontend/

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T011 Create database connection and async session management in backend/src/db/session.py
- [x] T012 Create Alembic configuration for migrations in backend/alembic.ini and backend/alembic/
- [x] T013 [P] Create base SQLAlchemy model with UUID primary key mixin in backend/src/models/base.py
- [x] T014 [P] Create Pydantic settings configuration in backend/src/core/config.py
- [x] T015 [P] Create security utilities (password hashing, JWT creation/validation) in backend/src/core/security.py
- [x] T016 Create FastAPI app instance with CORS middleware in backend/src/main.py
- [x] T017 [P] Create API router structure in backend/src/api/routes/__init__.py
- [x] T018 [P] Create database session dependency in backend/src/api/deps/database.py
- [x] T019 [P] Create error handling middleware in backend/src/api/middleware/errors.py
- [x] T020 [P] Create audit logging service in backend/src/services/audit.py
- [x] T021 Create AuditLog model in backend/src/models/audit_log.py
- [x] T022 [P] Create TypeScript API client base in frontend/src/services/api.ts
- [x] T023 [P] Create React Router configuration in frontend/src/App.tsx
- [x] T024 [P] Create Layout component with sidebar placeholder in frontend/src/components/layout/Layout.tsx
- [x] T025 Create initial Alembic migration for audit_log table in backend/alembic/versions/

**Checkpoint**: Foundation ready - user story implementation can begin

---

## Phase 3: User Story 1 - Secure User Authentication (Priority: P1) 🎯 MVP

**Goal**: Users can log in with email/password, receive JWT tokens, sessions expire after 30 minutes of inactivity, accounts lock after 5 failed attempts

**Independent Test**: Create user via seed, login with valid credentials, verify token returned, verify session timeout

### Implementation for User Story 1

- [x] T026 [P] [US1] Create User model with email, password_hash, is_active, locked_until, failed_attempts in backend/src/models/user.py
- [x] T027 [P] [US1] Create user Pydantic schemas (LoginRequest, AuthResponse, CurrentUser) in backend/src/schemas/auth.py
- [x] T028 [US1] Create AuthService with login, logout, validate_token, refresh_token methods in backend/src/services/auth.py
- [x] T029 [US1] Implement account lockout logic (5 attempts, 15 min lock) in backend/src/services/auth.py
- [x] T030 [US1] Create current_user dependency for protected routes in backend/src/api/deps/auth.py
- [x] T031 [US1] Implement POST /auth/login endpoint in backend/src/api/routes/auth.py
- [x] T032 [US1] Implement POST /auth/logout endpoint in backend/src/api/routes/auth.py
- [x] T033 [US1] Implement GET /auth/me endpoint in backend/src/api/routes/auth.py
- [x] T034 [US1] Implement POST /auth/refresh endpoint in backend/src/api/routes/auth.py
- [x] T035 [US1] Add auth routes to API router in backend/src/api/routes/__init__.py
- [x] T036 [US1] Create Alembic migration for users table in backend/alembic/versions/
- [x] T037 [US1] Integrate audit logging for login success/failure events in backend/src/services/auth.py
- [x] T038 [P] [US1] Create auth store for token management in frontend/src/stores/authStore.ts
- [x] T039 [P] [US1] Create auth service with login, logout, getCurrentUser in frontend/src/services/auth.ts
- [x] T040 [P] [US1] Create LoginPage component with email/password form in frontend/src/pages/LoginPage.tsx
- [x] T041 [US1] Create ProtectedRoute component for auth guards in frontend/src/components/common/ProtectedRoute.tsx
- [x] T042 [US1] Integrate auth flow with Router (redirect to login if not authenticated) in frontend/src/App.tsx
- [x] T043 [P] [US1] Create DashboardPage placeholder in frontend/src/pages/DashboardPage.tsx
- [x] T044 [US1] Create database seed script with admin user in backend/src/db/seed.py

**Checkpoint**: User can log in, receive token, access protected routes, session times out

---

## Phase 4: User Story 2 - Role-Based Access Control (Priority: P1)

**Goal**: Roles contain permissions, users have multiple roles, effective permissions = union, protected endpoints check permissions, UI elements filtered

**Independent Test**: Create roles with different permissions, assign to user, verify endpoint access denied/allowed based on permissions

### Implementation for User Story 2

- [x] T045 [P] [US2] Create Permission model in backend/src/models/permission.py
- [x] T046 [P] [US2] Create Role model with permissions relationship in backend/src/models/role.py
- [x] T047 [P] [US2] Create user_roles junction table in backend/src/models/user_roles.py
- [x] T048 [P] [US2] Create role_permissions junction table in backend/src/models/role_permissions.py
- [x] T049 [US2] Add roles relationship to User model in backend/src/models/user.py
- [x] T050 [P] [US2] Create role/permission Pydantic schemas in backend/src/schemas/roles.py
- [x] T051 [US2] Create PermissionService for checking user permissions in backend/src/services/permission.py
- [x] T052 [US2] Create require_permission dependency decorator in backend/src/api/deps/permissions.py
- [x] T053 [US2] Implement GET /roles endpoint in backend/src/api/routes/roles.py
- [x] T054 [US2] Implement POST /roles endpoint in backend/src/api/routes/roles.py
- [x] T055 [US2] Implement GET /roles/{roleId} endpoint in backend/src/api/routes/roles.py
- [x] T056 [US2] Implement PATCH /roles/{roleId} endpoint in backend/src/api/routes/roles.py
- [x] T057 [US2] Implement DELETE /roles/{roleId} with cascade in backend/src/api/routes/roles.py
- [x] T058 [US2] Implement PUT /roles/{roleId}/permissions endpoint in backend/src/api/routes/roles.py
- [x] T059 [US2] Implement GET /permissions endpoint in backend/src/api/routes/roles.py
- [x] T060 [US2] Add role routes to API router in backend/src/api/routes/__init__.py
- [x] T061 [US2] Create Alembic migration for permissions, roles, user_roles, role_permissions tables in backend/alembic/versions/
- [x] T062 [US2] Update seed script with default permissions and roles in backend/src/db/seed.py
- [x] T063 [US2] Update CurrentUser response to include effective permissions in backend/src/schemas/auth.py
- [x] T064 [US2] Update GET /auth/me to return user permissions in backend/src/api/routes/auth.py
- [x] T065 [P] [US2] Create usePermissions hook for permission checks in frontend/src/hooks/usePermissions.ts
- [x] T066 [P] [US2] Create PermissionGate component for conditional rendering in frontend/src/components/common/PermissionGate.tsx
- [x] T067 [P] [US2] Create RolesPage for role management in frontend/src/pages/RolesPage.tsx
- [x] T068 [US2] Create RoleForm component for create/edit role in frontend/src/components/roles/RoleForm.tsx
- [x] T069 [US2] Create PermissionSelector component in frontend/src/components/roles/PermissionSelector.tsx

**Checkpoint**: Permissions enforced on endpoints, UI filters based on permissions, role CRUD works

---

## Phase 5: User Story 3 - User Management (Priority: P2)

**Goal**: Admins can create, view, update, deactivate users and assign roles

**Independent Test**: Create user via admin UI, modify details, assign role, deactivate, verify login blocked

### Implementation for User Story 3

- [x] T070 [P] [US3] Create user Pydantic schemas (CreateUserRequest, UpdateUserRequest, UserList) in backend/src/schemas/users.py
- [x] T071 [US3] Create UserService with CRUD operations in backend/src/services/user.py
- [x] T072 [US3] Implement GET /users endpoint with pagination in backend/src/api/routes/users.py
- [x] T073 [US3] Implement POST /users endpoint in backend/src/api/routes/users.py
- [x] T074 [US3] Implement GET /users/{userId} endpoint in backend/src/api/routes/users.py
- [x] T075 [US3] Implement PATCH /users/{userId} endpoint in backend/src/api/routes/users.py
- [x] T076 [US3] Implement POST /users/{userId}/deactivate endpoint in backend/src/api/routes/users.py
- [x] T077 [US3] Implement POST /users/{userId}/reactivate endpoint in backend/src/api/routes/users.py
- [x] T078 [US3] Implement POST /users/{userId}/unlock endpoint in backend/src/api/routes/users.py
- [x] T079 [US3] Implement GET /users/{userId}/roles endpoint in backend/src/api/routes/users.py
- [x] T080 [US3] Implement PUT /users/{userId}/roles endpoint in backend/src/api/routes/users.py
- [x] T081 [US3] Add users routes to API router in backend/src/api/routes/__init__.py
- [x] T082 [US3] Add permission checks (users:read, users:write, users:delete) to user endpoints in backend/src/api/routes/users.py
- [x] T083 [US3] Integrate audit logging for user CRUD operations in backend/src/services/user.py
- [x] T084 [P] [US3] Create UsersPage with user list in frontend/src/pages/UsersPage.tsx
- [x] T085 [P] [US3] Create UserTable component with pagination in frontend/src/components/users/UserTable.tsx
- [x] T086 [US3] Create UserForm component for create/edit user in frontend/src/components/users/UserForm.tsx
- [x] T087 [US3] Create UserRoleAssignment component in frontend/src/components/users/UserRoleAssignment.tsx
- [x] T088 [US3] Create UserDetailPage for viewing/editing single user in frontend/src/pages/UserDetailPage.tsx

**Checkpoint**: Full user CRUD via admin UI, role assignment works, audit trail created

---

## Phase 6: User Story 4 - Excel Data Import (Priority: P2)

**Goal**: Upload Excel files, validate data, import with progress tracking, rollback on critical errors

**Independent Test**: Upload valid Excel file, verify data imported; upload invalid file, verify error feedback

### Implementation for User Story 4

- [ ] T089 [P] [US4] Create ImportJob model in backend/src/models/import_job.py
- [ ] T090 [P] [US4] Create import Pydantic schemas (ImportJob, ImportJobList, ImportError) in backend/src/schemas/import.py
- [ ] T091 [US4] Create Alembic migration for import_jobs table in backend/alembic/versions/
- [ ] T092 [US4] Create ImportService with file validation, processing, progress tracking in backend/src/services/import_service.py
- [ ] T093 [US4] Implement Excel parsing with pandas/openpyxl in backend/src/services/import_service.py
- [ ] T094 [US4] Implement import queue for sequential processing per user in backend/src/services/import_service.py
- [ ] T095 [US4] Implement rollback on critical errors in backend/src/services/import_service.py
- [ ] T096 [US4] Implement POST /import endpoint (file upload) in backend/src/api/routes/import.py
- [ ] T097 [US4] Implement GET /import/jobs endpoint in backend/src/api/routes/import.py
- [ ] T098 [US4] Implement GET /import/jobs/{jobId} endpoint in backend/src/api/routes/import.py
- [ ] T099 [US4] Add import routes to API router in backend/src/api/routes/__init__.py
- [ ] T100 [US4] Add permission check (import:execute) to import endpoints in backend/src/api/routes/import.py
- [ ] T101 [US4] Integrate audit logging for import events in backend/src/services/import_service.py
- [ ] T102 [P] [US4] Create ImportPage with file upload in frontend/src/pages/ImportPage.tsx
- [ ] T103 [P] [US4] Create FileUpload component in frontend/src/components/import/FileUpload.tsx
- [ ] T104 [US4] Create ImportJobList component with progress display in frontend/src/components/import/ImportJobList.tsx
- [ ] T105 [US4] Create ImportErrorDisplay component in frontend/src/components/import/ImportErrorDisplay.tsx
- [ ] T106 [US4] Implement polling for import job status in frontend/src/pages/ImportPage.tsx

**Checkpoint**: Excel upload works, validation errors displayed, successful imports show in system

---

## Phase 7: User Story 5 - Dynamic Module Navigation (Priority: P3)

**Goal**: Sidebar shows only modules user has permission for, new modules added via database without code changes

**Independent Test**: Configure module with specific permission, verify user with/without permission sees/doesn't see it

### Implementation for User Story 5

- [ ] T107 [P] [US5] Create Module model with parent_id for nesting in backend/src/models/module.py
- [ ] T108 [P] [US5] Create module_permissions junction table in backend/src/models/module_permissions.py
- [ ] T109 [P] [US5] Create module Pydantic schemas in backend/src/schemas/modules.py
- [ ] T110 [US5] Create Alembic migration for modules, module_permissions tables in backend/alembic/versions/
- [ ] T111 [US5] Create ModuleService with permission-filtered retrieval in backend/src/services/module.py
- [ ] T112 [US5] Implement GET /modules endpoint (filtered by user permissions) in backend/src/api/routes/modules.py
- [ ] T113 [US5] Implement GET /modules/all endpoint (admin) in backend/src/api/routes/modules.py
- [ ] T114 [US5] Implement POST /modules/all endpoint in backend/src/api/routes/modules.py
- [ ] T115 [US5] Implement PATCH /modules/{moduleId} endpoint in backend/src/api/routes/modules.py
- [ ] T116 [US5] Implement DELETE /modules/{moduleId} endpoint in backend/src/api/routes/modules.py
- [ ] T117 [US5] Add module routes to API router in backend/src/api/routes/__init__.py
- [ ] T118 [US5] Update seed script with default modules in backend/src/db/seed.py
- [ ] T119 [P] [US5] Create Sidebar component that fetches /modules in frontend/src/components/layout/Sidebar.tsx
- [ ] T120 [P] [US5] Create SidebarItem component with nested support in frontend/src/components/layout/SidebarItem.tsx
- [ ] T121 [US5] Update Layout to use dynamic Sidebar in frontend/src/components/layout/Layout.tsx
- [ ] T122 [P] [US5] Create ModulesAdminPage for module configuration in frontend/src/pages/ModulesAdminPage.tsx
- [ ] T123 [US5] Create ModuleForm component in frontend/src/components/modules/ModuleForm.tsx

**Checkpoint**: Sidebar dynamically shows permitted modules, admin can configure modules via UI

---

## Phase 8: User Story 6 - Hardware Security Key Enrollment (Priority: P3)

**Goal**: Users can register FIDO2 keys for passwordless login, admin can reset FIDO2 for locked-out users

**Independent Test**: Register hardware key, log out, log in using only key (no password)

### Implementation for User Story 6

- [ ] T124 [P] [US6] Create FIDO2Credential model in backend/src/models/fido2_credential.py
- [ ] T125 [P] [US6] Create WebAuthn Pydantic schemas in backend/src/schemas/webauthn.py
- [ ] T126 [US6] Create Alembic migration for fido2_credentials table in backend/alembic/versions/
- [ ] T127 [US6] Create WebAuthnService using py_webauthn library in backend/src/services/webauthn.py
- [ ] T128 [US6] Implement POST /auth/webauthn/register/options endpoint in backend/src/api/routes/auth.py
- [ ] T129 [US6] Implement POST /auth/webauthn/register/verify endpoint in backend/src/api/routes/auth.py
- [ ] T130 [US6] Implement POST /auth/webauthn/login/options endpoint in backend/src/api/routes/auth.py
- [ ] T131 [US6] Implement POST /auth/webauthn/login/verify endpoint in backend/src/api/routes/auth.py
- [ ] T132 [US6] Implement GET /users/{userId}/credentials endpoint in backend/src/api/routes/users.py
- [ ] T133 [US6] Implement DELETE /users/{userId}/credentials/{credentialId} endpoint in backend/src/api/routes/users.py
- [ ] T134 [US6] Implement POST /users/{userId}/reset-fido2 endpoint (admin) in backend/src/api/routes/users.py
- [ ] T135 [US6] Integrate audit logging for FIDO2 events in backend/src/services/webauthn.py
- [ ] T136 [P] [US6] Create SecuritySettingsPage for key management in frontend/src/pages/SecuritySettingsPage.tsx
- [ ] T137 [P] [US6] Create FIDO2KeyList component in frontend/src/components/security/FIDO2KeyList.tsx
- [ ] T138 [US6] Create RegisterKeyButton with WebAuthn API integration in frontend/src/components/security/RegisterKeyButton.tsx
- [ ] T139 [US6] Update LoginPage with FIDO2 login option in frontend/src/pages/LoginPage.tsx
- [ ] T140 [US6] Create webauthn service for browser API calls in frontend/src/services/webauthn.ts

**Checkpoint**: FIDO2 registration and login works, admin can reset locked-out users

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements affecting multiple user stories

- [ ] T141 [P] Create API documentation in backend README in backend/README.md
- [ ] T142 [P] Create frontend documentation in frontend README in frontend/README.md
- [ ] T143 [P] Implement GET /audit endpoint for audit log queries in backend/src/api/routes/audit.py
- [ ] T144 [P] Create AuditLogPage in frontend in frontend/src/pages/AuditLogPage.tsx
- [ ] T145 Add rate limiting to auth endpoints using slowapi in backend/src/api/middleware/rate_limit.py
- [ ] T146 Add CSRF protection for cookie-based auth in backend/src/api/middleware/csrf.py
- [ ] T147 [P] Create error boundary component in frontend/src/components/common/ErrorBoundary.tsx
- [ ] T148 [P] Create loading spinner component in frontend/src/components/common/LoadingSpinner.tsx
- [ ] T149 Run quickstart.md validation - verify all setup steps work
- [ ] T150 Security review - verify no exposed secrets, proper validation, no injection vulnerabilities

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational
- **User Story 2 (Phase 4)**: Depends on Foundational, light dependency on User model from US1
- **User Story 3 (Phase 5)**: Depends on US1 (User model) and US2 (permissions)
- **User Story 4 (Phase 6)**: Depends on US1 (auth) and US2 (permissions)
- **User Story 5 (Phase 7)**: Depends on US2 (permissions)
- **User Story 6 (Phase 8)**: Depends on US1 (User model, auth flow)
- **Polish (Phase 9)**: Depends on all user stories complete

### User Story Dependencies

```
Foundational ──┬──► US1 (Auth) ──────────────┬──► US3 (User Mgmt)
               │                             │
               ├──► US2 (RBAC) ──────────────┼──► US4 (Import)
               │         │                   │
               │         └───────────────────┼──► US5 (Modules)
               │                             │
               └─────────────────────────────┴──► US6 (FIDO2)
```

### Parallel Opportunities

**Phase 1 (Setup)**: T003-T010 all parallelizable
**Phase 2 (Foundational)**: T013-T024 mostly parallelizable
**After Foundational**: US1 and US2 can start in parallel (different models/endpoints)
**After US1+US2**: US3, US4, US5, US6 can all proceed in parallel

---

## Parallel Example: User Story 1

```bash
# Launch models in parallel:
Task: "Create User model in backend/src/models/user.py"
Task: "Create user Pydantic schemas in backend/src/schemas/auth.py"

# Launch frontend components in parallel:
Task: "Create auth store in frontend/src/stores/authStore.ts"
Task: "Create auth service in frontend/src/services/auth.ts"
Task: "Create LoginPage in frontend/src/pages/LoginPage.tsx"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (Authentication)
4. Complete Phase 4: User Story 2 (RBAC)
5. **STOP and VALIDATE**: Users can log in, permissions work
6. Deploy/demo as MVP

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 + US2 → Authentication + RBAC MVP
3. Add US3 → Admin can manage users
4. Add US4 → Excel import works
5. Add US5 → Dynamic navigation
6. Add US6 → FIDO2 support

---

## Summary

| Phase | Tasks | Parallel Tasks |
|-------|-------|----------------|
| Setup | 10 | 8 |
| Foundational | 15 | 10 |
| US1 - Authentication | 19 | 6 |
| US2 - RBAC | 25 | 6 |
| US3 - User Management | 19 | 3 |
| US4 - Excel Import | 18 | 4 |
| US5 - Modules | 17 | 5 |
| US6 - FIDO2 | 17 | 3 |
| Polish | 10 | 6 |
| **Total** | **150** | **51** |

**Suggested MVP**: Phase 1 + 2 + 3 + 4 (69 tasks) delivers working authentication with RBAC
