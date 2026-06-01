# Instalación

## Requisitos

- **Python 3.14+**
- **Docker** + Docker Compose (para Redis y Mailpit en local).
- Una **base de datos** alcanzable. El engine es agnóstico del motor (MySQL/MariaDB,
  PostgreSQL, Oracle, SQL Server, SQLite); se elige con `DATABASE_URL`.
- (Recomendado) [**uv**](https://docs.astral.sh/uv/) como gestor de entorno y deps.

## Opción A — con `uv` (recomendada)

```bash
uv sync
```

Crea el entorno y resuelve dependencias (incluidas las de desarrollo) desde
`pyproject.toml` / `uv.lock`. Para correr cualquier comando, antepón `uv run` (no
necesitas activar el venv):

```bash
uv run python jornal list
uv run pytest
```

Solo producción (sin herramientas de dev):

```bash
uv sync --no-dev
```

## Opción B — Python + venv (pip)

```bash
python3.14 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -e .                   # dependencias de ejecución
pip install --group dev            # herramientas de dev (pip >= 25.1)
# pip más viejo:  pip install pytest ruff mypy import-linter
```

Con el venv **activado**, corre los comandos **sin** el prefijo `uv run`.

## Drivers de base de datos

`pymysql` (MySQL/MariaDB) ya viene en el core. Para otros motores, instala su extra:

```bash
uv sync --extra postgres      # PostgreSQL (psycopg v3)
uv sync --extra oracle        # Oracle (oracledb)
uv sync --extra mssql         # SQL Server (pyodbc; requiere el ODBC Driver del SO)
```

Con pip: `pip install ".[postgres]"`.

El motor se elige con el prefijo de `DATABASE_URL` (ver [Base de datos](16-base-de-datos.md)):

```
mysql+pymysql://...        postgresql+psycopg://...      oracle+oracledb://...
mssql+pyodbc://...         sqlite:///app.db
```

## Configuración mínima

```bash
cp .env.example .env
```

Como mínimo necesitas `DATABASE_URL` (es la única variable **sin** default). Ajusta el
resto según tu entorno. Ver [Configuración](03-configuracion.md).

## Levantar la infraestructura

Docker solo corre infraestructura (Redis + Mailpit; RabbitMQ opcional). La app corre
en el host.

```bash
docker compose up -d        # Redis (6379) + Mailpit (SMTP 1025, UI http://localhost:8025)
```

## Verificar la instalación

```bash
uv run python jornal list                 # debe listar los comandos
uv run pytest                             # la suite debe pasar (sin BD)
uv run python jornal serve                # levanta la API en http://localhost:8000
```

## Siguiente paso

[Configuración](03-configuracion.md).
