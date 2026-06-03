# Autenticación y autorización

milpa trae auth **propia** (login, hash de password, emisión de tokens, sesión, roles) y, además,
**validación de tokens externos de Laravel Passport** para migrar. El modelo es el de **Laravel
Sanctum**: dos carriles a la vez —

- **JWT (API)** — bearer tokens que milpa emite (HS256). Para frontends SEPARADOS (SPA/móvil).
- **Sesión cookie + CSRF (browser)** — cookie firmada (Secure/HttpOnly/SameSite=Lax). Para HTMX/
  server-rendered de primera-parte.

Todo vive en `milpa/Core/Auth`. Hay un demo corrible que usa los dos carriles: ver el
[Quickstart del demo](https://github.com/calcifux/milpa#-demo-corrible).

## Guards

Un **guard** resuelve el usuario autenticado desde el request. milpa trae tres:

| Guard | Mecanismo | Para |
|-------|-----------|------|
| `jwt` | `Authorization: Bearer <jwt>` (propio, HS256) | API / frontend separado |
| `session` | cookie de sesión firmada | browser / HTMX |
| `passport` | `Authorization: Bearer <jwt>` (RS256 EXTERNO de Laravel Passport) | migración |

`AUTH_GUARD` (.env) fija el default; o eliges el guard por ruta con `guarded("jwt")` /
`guarded("session")` (útil porque la misma app sirve los dos carriles).

## Hashing

```python
from milpa.Core.Auth import Hash

hashed = Hash.make("secreto")      # argon2id
Hash.verify("secreto", hashed)     # True — verifica argon2 y también bcrypt ($2y$ de Laravel)
```

`Hash.verify` acepta hashes **bcrypt de Laravel** (normaliza `$2y$`↔`$2b$`), así puedes migrar
los passwords existentes sin re-hashear a todos de golpe.

## El modelo User

milpa NO impone el esquema. Tu modelo cumple el contrato `Authenticatable` (id, hash de password,
roles); lo más fácil es heredar `AuthenticatableMixin` (asume columnas `id`/`password`/`roles`):

```python
class User(TimestampMixin, AuthenticatableMixin, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    password: Mapped[str] = mapped_column()
    roles: Mapped[str] = mapped_column(default="")  # CSV: "admin,editor"
```

`AUTH_USER_MODEL` (.env) apunta a ese modelo. El `SqlAlchemyUserProvider` lo usa por default; si
migras de una BD legacy, registra tu propio provider con `set_user_provider(...)`.

## Login

**API (JWT):**
```python
from milpa.Core.Auth import Auth

token = Auth.attempt(email, password)   # JWT (str) o None si las credenciales fallan
# -> el cliente manda luego: Authorization: Bearer <token>
```

**Browser (sesión cookie):**
```python
user = Auth.validate_credentials(email, password)
if user:
    Auth.login(request, user)    # guarda el id en la sesión firmada
# ...
Auth.logout(request)             # cierra la sesión
```

## Proteger rutas (autenticación)

```python
from milpa.Core.Auth import CurrentUser, authenticated, guarded, Authenticatable
from fastapi import Depends

# Guard por default (AUTH_GUARD):
def me(user: Authenticatable = CurrentUser): ...          # CurrentUser = Depends(authenticated)

# Guard EXPLÍCITO por carril:
def api_me(user: Authenticatable = Depends(guarded("jwt"))): ...
def web_me(user: Authenticatable = Depends(guarded("session"))): ...
```

- Sin/!con token → `401` (`UnauthorizedError` → `application/problem+json`).
- `Auth.user()` / `Auth.id()` / `Auth.check()` leen el usuario del request actual (contextvar), útil
  en servicios y templates sin pasarlo a mano.

## Autorización: RBAC (roles) + ABAC (policies)

**RBAC — por rol:**
```python
from milpa.Core.Auth import require_roles, Roles
from fastapi import Depends

def admin_only(user = Depends(require_roles("admin", guard="jwt"))): ...   # 403 si no tiene el rol

@Controller("/admin")
class AdminController:
    @Get("/users")
    @Roles("admin")                 # azúcar para controllers @Controller
    def users(self): ...
```

**ABAC — por policy (atributos del recurso):**
```python
from milpa.Core.Auth import Gate

# 1) Registra la policy (típicamente en app/Modules/<X>/Policies.py):
Gate.define("note.update", lambda user, note: note.owner_id == user.get_auth_identifier())

# 2) Autoriza DENTRO del handler/servicio, tras cargar el recurso:
Gate.authorize("note.update", note)        # ForbiddenError (403) si no aplica
# Gate.allows("note.update", note) -> bool
```

Para abilities SIN recurso (p. ej. `note.create`), usa `@Can("note.create")` sobre el método del
controller. Sin policy registrada para una ability → **denegado** (seguro por default).

## CSRF (solo carril sesión)

El carril cookie va con protección **CSRF double-submit** automática (`CsrfMiddleware`):

- En cada método NO-seguro (POST/PUT/PATCH/DELETE) **con cookie de sesión**, exige el header
  `X-CSRF-Token` igual a la cookie `milpa_csrf`. El front/HTMX la reenvía solo (ver el `layout` del
  demo). EXENTAS: requests con `Authorization: Bearer` (API) y sin sesión (login/registro, clientes
  API por JSON). Rechazo → `403 problem+json`.
- Config: `CSRF_ENABLED`, `CSRF_COOKIE`, `CSRF_HEADER`; sesión: `SESSION_SECRET` (obligatorio para
  el guard `session`), `SESSION_SECURE` (=`true` en prod/HTTPS), `SESSION_SAME_SITE`.

## Migrar desde Laravel (Passport, RS256)

Cuando el emisor de tokens sigue siendo el legacy, milpa **valida** (no emite): copia la llave
**pública** RS256 (`storage/oauth-public.key`) a `secrets/` y apunta `PASSPORT_PUBLIC_KEY_PATH`. Usa
el guard `passport` (resuelve el user por el claim `sub` vía tu provider) o las dependencies
clásicas de scopes:

```python
from milpa.Core.Auth import get_current_token, require_scopes, TokenPrincipal

def profile(principal: TokenPrincipal = Depends(get_current_token)): ...
def admin(principal: TokenPrincipal = Depends(require_scopes("admin"))): ...
```

| Situación | Código |
|-----------|--------|
| Sin llave pública configurada | `503` (infra: te falta el secret) |
| Token inválido / expirado / firma mala | `401` |
| Faltan scopes | `403` |

La revocación queda como punto de extensión (hoy valida firma/expiración/audiencia).

## Variables de entorno

```bash
AUTH_GUARD=jwt                 # jwt | session | passport (default)
AUTH_USER_MODEL=app.Models.User.User
JWT_SECRET=                    # OBLIGATORIO para emitir/validar JWT propios
JWT_ALGORITHM=HS256
JWT_TTL_SECONDS=3600
SESSION_SECRET=                # OBLIGATORIO para el guard 'session'
SESSION_SECURE=false           # true en prod (HTTPS)
SESSION_SAME_SITE=lax
CSRF_ENABLED=true
PASSPORT_PUBLIC_KEY_PATH=/secrets/oauth-public.key   # solo para migrar (guard passport)
```

## Siguiente paso

[Base de datos](16-base-de-datos.md).
