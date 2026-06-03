# Base de datos: configuración del motor

La capa de datos de milpa es **agnóstica del motor SQL**. Eliges la base con
`DATABASE_URL` y el resto del código no cambia. Detrás está SQLAlchemy 2.0, con todo lo
específico de cada dialecto **aislado** en `milpa/Core/Database/Session.py`.

## Elegir el motor: `DATABASE_URL`

El prefijo de la URL determina el dialecto (y el driver):

```
mysql+pymysql://user:pass@host:3306/db          # MySQL / MariaDB (uv sync --extra mysql)
postgresql+psycopg://user:pass@host:5432/db     # PostgreSQL   (uv sync --extra postgres)
oracle+oracledb://user:pass@host:1521/?service_name=db   # Oracle (--extra oracle)
mssql+pyodbc://user:pass@host/db?driver=ODBC+Driver+18   # SQL Server (--extra mssql)
sqlite:///app.db                                # SQLite (dev/tests)
```

milpa detecta el backend automáticamente (`make_url(...).get_backend_name()`). No hay
nada hardcodeado: cambiar de motor es cambiar la URL (y, si aplica, instalar su driver —
ver [Instalación](02-instalacion.md)).

## El engine y el pool

`Session.py` construye el `engine` con kwargs que difieren **por motor**:

- **SQLite**: `check_same_thread=False` (la conexión cruza hilos en FastAPI/workers); si
  es en memoria, `StaticPool` (una sola conexión compartida).
- **Cliente-servidor** (MySQL/PostgreSQL/Oracle/MSSQL): `pool_pre_ping=True` (verifica la
  conexión antes de usarla) y `pool_recycle=3600` (recicla cada hora; los servidores
  cierran conexiones longevas).

## Zona horaria por conexión

Cada vez que se abre una conexión, milpa fija su zona horaria a la de la app
(`TIMEZONE`), vía un event hook `connect`. Así `NOW()` / `func.now()` (los timestamps
automáticos) salen en hora local **sin** que Python intervenga. La sentencia depende del
motor:

| Motor | Sentencia | Nota |
|-------|-----------|------|
| MySQL/MariaDB | `SET time_zone = '-06:00'` | offset (los nombres IANA exigen cargar tz tables) |
| PostgreSQL | `SET TIME ZONE 'America/Mexico_City'` | nombre IANA (Postgres trae las zonas) |
| Oracle | `ALTER SESSION SET TIME_ZONE = '-06:00'` | offset vía ALTER |
| SQLite / SQL Server | (sin zona por sesión) | en SQLite los timestamps caen a UTC; afecta solo dev/tests |

Por eso conviene **fijar `TIMEZONE`** explícito en el `.env` de un servidor (suele estar
en UTC). Ver [Configuración](03-configuracion.md).

## `SessionLocal`

```python
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
```

`autocommit=False` (el commit es explícito, lo gobierna `@transactional`/`session_scope`)
y `autoflush=False` (flush explícito, más predecible). No la usas directo: la capa
transaccional la envuelve (ver [Repositorios y transacciones](18-repositorios-y-transacciones.md)).

## ¿Crear tablas?

`AUTO_CREATE_TABLES` (default `false`). Si es `true`, el lifespan crea las tablas al
arrancar. **Contra una BD legacy compartida, déjalo en `false`**: milpa no debe crear ni
alterar el esquema. Para esquemas **nuevos**, versiona los cambios con migraciones (Alembic),
no con `create_all`.

## Migraciones (Alembic)

Para una BD **propia** (greenfield), gestiona el esquema con migraciones versionadas. milpa
trae Alembic integrado y operado por `jornal` (estilo `php artisan migrate`):

```bash
uv run python jornal migrate make -m "crear tabla facturas"  # genera la revisión (autogenerate)
uv run python jornal migrate run                              # aplica las pendientes (upgrade head)
uv run python jornal migrate status                          # revisión actual + historial
uv run python jornal migrate rollback                        # revierte una (downgrade -1)
```

Cómo encaja con el resto del framework (sin duplicar config):

- **Una sola fuente de conexión.** No hay `alembic.ini`: la config se arma en código
  (`milpa/Core/Database/Migrations.py`) y `migrations/env.py` toma la BD de `DATABASE_URL`
  (Settings) reusando el **engine** del framework. Cambias de motor sin tocar Alembic.
- **Autogenerate desde tus modelos.** `env.py` llama a `import_all_models()` (el mismo
  discovery de la app) para poblar `Base.metadata`; el `make` compara esos modelos contra el
  esquema real. La `naming_convention` de `Base` hace los nombres de índices/constraints
  reproducibles. `compare_type=True` detecta también cambios de TIPO de columna.
- **Revisa antes de aplicar.** El archivo cae en `migrations/versions/` (versionado en git);
  `migrate make` NO toca la BD — solo `migrate run` aplica.
- **BD legacy:** no generes migraciones de tablas que no administras. Úsalo solo para las
  tablas NUEVAS del proyecto.

### Catálogos fijos: siémbralos en la migración (`op.bulk_insert`)

Para datos **de catálogo** que son parte del esquema (estados, tipos, roles fijos: cambian con el
código, no con el uso), no necesitas un seeder aparte — siémbralos **dentro de la propia migración**
con `op.bulk_insert`. Así el catálogo viaja versionado con el `upgrade`/`downgrade` y queda igual en
todos los entornos:

```python
def upgrade() -> None:
    estatus = op.create_table(
        "estatus_factura",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("clave", sa.String(20), nullable=False, unique=True),
        sa.Column("etiqueta", sa.String(60), nullable=False),
    )
    op.bulk_insert(  # el catálogo es parte del esquema → va aquí, no en un seeder
        estatus,
        [
            {"id": 1, "clave": "borrador", "etiqueta": "Borrador"},
            {"id": 2, "clave": "timbrada", "etiqueta": "Timbrada"},
            {"id": 3, "clave": "cancelada", "etiqueta": "Cancelada"},
        ],
    )


def downgrade() -> None:
    op.drop_table("estatus_factura")
```

Regla práctica: **catálogo fijo → migración** (`op.bulk_insert`); **datos de ejemplo / demo o
volumen variable → seeder + factory** (`jornal db seed`, Faker). Ver [La consola jornal](08-consola-jornal.md).

## ¿Y NoSQL?

Hoy la capa cubre **SQL**. NoSQL (Mongo, etc.) está **diferido on-demand**: cuando se
necesite, se implementa detrás del mismo patrón `Repository`. No hay un adapter NoSQL
especulativo.

## Siguiente paso

[Modelos](17-modelos.md).
