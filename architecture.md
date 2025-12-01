# Architecture Client/Serveur Proposée

## 1. Vue d'ensemble de l'architecture

L'architecture générale repose sur :

-   **Backend** : API REST/JSON (FastAPI)
-   **Frontend** : Application web SPA dans Google Chrome
-   **Client optionnel** : Scripts ou outils en WinPython/Java
-   **Base de données** : PostgreSQL

Flux général :

Utilisateur → Chrome → SPA → API Backend → Base de données\
Authentification : email/mot de passe ou FIDO2 (SoloKey/YubiKey).\
Import Excel : upload via interface.\
Intégration Sage X3 : prévue mais non implémentée.

------------------------------------------------------------------------

## 2. Stack Serveur

### 2.1 Langage et framework

-   Python 3.x
-   FastAPI
-   Serveur ASGI : Uvicorn

### 2.2 Base de données

-   PostgreSQL
-   ORM : SQLAlchemy ou Tortoise ORM

Tables principales : - users - roles - user_roles - permissions -
role_permissions - audit_log

### 2.3 API REST

Endpoints principaux : - /auth/login - /auth/register (optionnel) -
/auth/webauthn/register - /auth/webauthn/verify - /users - /roles -
/excel/import - /sage-x3/export - /menus

------------------------------------------------------------------------

## 3. Côté Client

### 3.1 Application web (Frontend)

-   SPA en React ou Vue.js\
-   UI avec Material UI / Bootstrap / Tailwind\
-   Layout comprenant :
    -   Sidebar dynamique
    -   Zone de contenu
    -   Header optionnel

Pages principales : - /login\
- /dashboard\
- /utilisateurs\
- /roles\
- /import-excel

### 3.2 WinPython / Java

-   Exécution de scripts techniques\
-   Clients API internes\
-   Connecteurs éventuels

------------------------------------------------------------------------

## 4. Authentification

### 4.1 Email / Mot de passe

-   Auth via /auth/login\
-   Mot de passe hashé (bcrypt, argon2)\
-   JWT ou session HTTPOnly

### 4.2 FIDO2 / WebAuthn (SoloKey, YubiKey)

Backend : - Gestion des challenges\
- Stockage public key + credential ID

Frontend : - navigator.credentials.create\
- navigator.credentials.get

Flux : - Enrôlement : /auth/webauthn/register\
- Login : /auth/webauthn/verify

------------------------------------------------------------------------

## 5. Rôles, Droits, Excel, Sage X3

### 5.1 RBAC

-   Un utilisateur peut avoir plusieurs rôles\
-   Rôles → permissions\
-   Filtrage des endpoints\
-   Filtrage de l'affichage de la sidebar

### 5.2 Import Excel

-   Upload via /excel/import\
-   Traitement Python avec pandas/openpyxl\
-   Validation\
-   Insertion en base

### 5.3 Sage X3

-   Module séparé\
-   Endpoints prévus : /sage-x3/export, /sage-x3/import\
-   Implémentation ultérieure

------------------------------------------------------------------------

## 6. Extensibilité via la barre latérale

Table modules : - id\
- code\
- label\
- route_frontend\
- icon\
- required_permissions

Fonctionnement : - Le backend renvoie les modules accessibles via
/menus\
- Le frontend génère dynamiquement la sidebar\
- Ajouter une fonctionnalité = créer un module + page + endpoint backend

------------------------------------------------------------------------

Fin du document.
