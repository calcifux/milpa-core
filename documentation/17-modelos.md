# Modelos

Los modelos son clases SQLAlchemy 2.0 que heredan de `Base`. Viven en `app/Models/`
(compartidos por todos los módulos), un modelo por archivo, estilo Eloquent.

## Definir un modelo

```python
# app/Models/Invoice.py
from decimal import Decimal
from sqlalchemy import String, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.Core.Database import Base, TimestampMixin, SoftDeleteMixin

class Invoice(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True)
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2))
```

`Base` (de `app/Core/Database`) es la `DeclarativeBase` del proyecto. Trae una
`naming_convention` estable para índices/constraints (migraciones Alembic reproducibles).

## Auto-discovery

`app/Models/__init__.py` importa **todos** los modelos de la carpeta al cargarse
(`pkgutil`). Esto es necesario porque SQLAlchemy debe tener registrados todos los modelos
para resolver las relaciones declaradas por string (`Company` → `CompanyAddress`) sin
depender del orden de imports.

Consecuencia práctica: **agregar un modelo = crear su archivo**. No editas el `__init__`.
Y `from app.Models.Invoice import Invoice` basta para que todo el registro quede cargado.

(Contrasta con `app/Dictionaries`, que son constantes y no necesitan registro: se
importan por submódulo. Ver [Estructura](04-estructura-directorios.md).)

## Mixins: timestamps y soft delete

Ambos son **opt-in por modelo**: solo los hereda un modelo cuya tabla tiene las columnas.

### `TimestampMixin`

Agrega dos columnas que la **BD** llena (server-side, en la zona de la app):

| Columna | Comportamiento |
|---------|----------------|
| `created_at` | se setea al INSERT (`func.now()`). |
| `updated_at` | se setea al INSERT y se refresca en cada UPDATE (= `$table->timestamps()`). |

```python
class Invoice(TimestampMixin, Base):
    ...
```

> En SQLite (tests) no hay zona por sesión → `func.now()` cae a UTC. En prod
> (Postgres/MySQL) sale en hora local. Ver [Base de datos](16-base-de-datos.md).

### `SoftDeleteMixin`

Borrado lógico (vía `sqlalchemy-easy-softdelete`). Agrega `deleted_at` y:

- **Filtra automáticamente** `deleted_at IS NULL` en todo SELECT (incluidas relaciones).
- Marca como borrado en vez de eliminar físicamente.

```python
class Invoice(TimestampMixin, SoftDeleteMixin, Base):
    ...
```

Para **incluir** borrados lógicos en una query puntual (= `withTrashed` de Laravel):

```python
session.execute(
    select(Invoice).execution_options(include_deleted=True)
).scalars().all()
```

Los catálogos sin estas columnas simplemente no heredan los mixins:

```python
class Moneda(Base):                       # sin timestamps ni soft delete
    __tablename__ = "monedas"
    codigo: Mapped[str] = mapped_column(String(3), primary_key=True)
```

## Relaciones

Relaciones SQLAlchemy normales. Como todos los modelos se auto-importan, puedes
declararlas por string sin preocuparte del orden:

```python
from sqlalchemy.orm import relationship, Mapped

class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[int] = mapped_column(primary_key=True)
    items: Mapped[list["InvoiceItem"]] = relationship(back_populates="invoice")
```

Para leer grafos de objetos sin caer en N+1 ni en `DetachedInstanceError`, usa eager
loading (`selectinload`) dentro del scope de sesión y devuelve un DTO. Ver
[Repositorios y transacciones](18-repositorios-y-transacciones.md).

## Siguiente paso

[Repositorios y transacciones](18-repositorios-y-transacciones.md).
