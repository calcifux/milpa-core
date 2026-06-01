# Repositorios y transacciones

milpa adopta un modelo de persistencia **estilo Spring Data / JPA**:

- **Repositorios** tipados (`Repository[Model, Id]`) con CRUD heredado — solo queries.
- **Escrituras** en servicios `@transactional` (commit/rollback automático).
- **Lecturas** con `@auto_session` (funcionan con o sin scope abierto).
- La **sesión es ambiente** (un contextvar), no se inyecta por constructor.

La división de responsabilidades: el Repository **consulta**, el Service **orquesta y
transacciona**.

## La sesión ambiente

La sesión vive en un contextvar scoped por request/task (como el `EntityManager`
thread-bound de Spring), **no** es global de proceso. Tres primitivos la gobiernan
(`app/Core/Database/Transactional.py`):

| Primitivo | Qué hace | Cuándo usarlo |
|-----------|----------|---------------|
| `current_session()` | Devuelve la sesión del scope; **error claro** si no hay. | dentro de un repo/servicio |
| `session_scope()` | Context manager: abre/cierra la sesión; **commits manuales**. | flujos con varios commits (lotes) |
| `@transactional` | Decorador: abre + **commit on success / rollback on exception**. | servicios de una transacción |
| `@auto_session` | Decorador: usa la sesión si hay; si no, abre una **efímera** (no commitea). | lecturas / queries de repo |

Todos son **join-or-create** (propagación `REQUIRED`): si ya hay sesión en el contextvar
(llamada anidada), la **reutilizan** y **no** la cierran/commitean — eso lo hace quien la
abrió. Esto hace que anidar servicios `@transactional` produzca **una sola** transacción.

## Definir un repositorio

```python
# app/Models/Repositories/InvoiceRepository.py
from sqlalchemy import select
from app.Core.Database import Repository
from app.Models.Invoice import Invoice

class InvoiceRepository(Repository[Invoice, int]):
    model = Invoice

    def find_by_numero(self, numero: str) -> Invoice | None:
        return self.session.execute(
            select(Invoice).where(Invoice.numero == numero)
        ).scalars().first()
```

- `model = Invoice` declara qué entidad gestiona.
- `self.session` encapsula `current_session()` — úsalo en tus queries custom; no llames
  `current_session()` a mano.
- Las **queries custom** (métodos públicos) se envuelven **automáticamente** con
  `@auto_session` (vía `__init_subclass__`): funcionan con o sin scope abierto. No pones
  el decorador a mano.

### CRUD heredado

| Método | Firma | Decorador |
|--------|-------|-----------|
| `get` | `get(entity_id: IdT) -> ModelT \| None` | `@auto_session` |
| `find_or_fail` | `find_or_fail(entity_id: IdT) -> ModelT` (lanza `ResourceNotFoundError` si no existe) | `@auto_session` |
| `all` | `all() -> Sequence[ModelT]` | `@auto_session` |
| `add` | `add(entity: ModelT) -> ModelT` (hace `flush()` para asignar PK) | `@transactional` |
| `first_or_create` | `first_or_create(where: dict, values: dict \| None = None) -> ModelT` | `@transactional` |
| `delete` | `delete(entity: ModelT) -> None` (lógico si hereda `SoftDeleteMixin`) | `@transactional` |

```python
repo = InvoiceRepository()
inv = repo.get(7)                 # abre sesión efímera si no hay scope; None si no existe
inv = repo.find_or_fail(7)        # = findOrFail de Eloquent: 404 (ResourceNotFoundError) si falta
todas = repo.all()                # filtra borradas lógicas (SoftDeleteMixin)
inv2 = repo.find_by_numero("INV-001")

# firstOrCreate: busca por `where`; si no hay, crea con where + values (extras solo-al-crear)
cliente = ClienteRepository().first_or_create({"rfc": "XAXX010101000"}, {"nombre": "Público"})
```

- **`find_or_fail`** evita el `if x is None: raise` repetido en cada service: el handler
  global convierte `ResourceNotFoundError` en un `404 {error_code, message, details}`.
- **`first_or_create`** es idempotente por `where`: devuelve el existente o crea uno nuevo
  (con su PK ya asignada vía `flush`). Como es `@transactional`, persiste o se une a la tx
  externa.

> Limitación honesta: no derivamos queries del **nombre** del método (el `findByX` de
> Spring). En Python sería frágil. Las queries custom llevan cuerpo explícito.

## Escribir: servicios `@transactional`

```python
# app/Modules/Billing/Services/InvoiceService.py
from decimal import Decimal
from app.Core.Database import transactional
from app.Models.Invoice import Invoice
from app.Models.Repositories.InvoiceRepository import InvoiceRepository

class InvoiceService:
    def __init__(self) -> None:
        self._invoices = InvoiceRepository()

    @transactional
    def crear(self, numero: str, monto: Decimal) -> Invoice:
        return self._invoices.add(Invoice(numero=numero, monto=monto))

    @transactional
    def marcar_pagada(self, invoice_id: int) -> None:
        inv = self._invoices.get(invoice_id)        # se une a esta transacción
        if inv is None:
            raise ValueError("no existe")
        inv.pagada = True                            # cambio tracked; flush+commit al salir
```

- Cada método `@transactional` abre sesión, commitea al terminar, o hace rollback si
  lanza.
- Las llamadas a repos dentro (`add`, `get`, queries) **se unen** a esa transacción.
- No necesitas `session.add()` para objetos ya cargados: SQLAlchemy trackea los cambios.

### Transacciones compuestas (anidadas)

```python
@transactional
def crear_pedido_con_factura(self, ...) -> None:
    self._invoices.crear(...)        # @transactional → se une, no commitea aparte
    self._stock.descontar(...)       # @transactional → se une
    # UN solo commit al final; si cualquiera lanza → rollback de TODO
```

## Leer fuera de una transacción

Un endpoint que lee y devuelve JSON no necesita `@transactional`: `repo.get()` abre una
sesión efímera (gracias a `@auto_session`). Pero **convierte a DTO dentro del scope**:

```python
@router.get("/invoices/{invoice_id}", response_model=InvoiceDTO)
def get_invoice(invoice_id: int) -> InvoiceDTO:
    inv = InvoiceRepository().get(invoice_id)
    if inv is None:
        raise HTTPException(status_code=404)
    return InvoiceDTO.model_validate(inv)   # serializa AQUÍ, con la sesión viva
```

## Control manual: `session_scope`

Para flujos con varios checkpoints de commit (procesos por lotes):

```python
from app.Core.Database import session_scope

def procesar_lote(ids: list[int]) -> None:
    repo = InvoiceRepository()
    with session_scope() as session:
        for i, inv_id in enumerate(ids):
            inv = repo.get(inv_id)              # se une al scope
            if inv:
                inv.procesada = True
            if (i + 1) % 100 == 0:
                session.commit()                # checkpoint cada 100
        session.commit()                        # final
```

Aquí los commits son tuyos (a diferencia de `@transactional`). Es el patrón para
preservar invariantes "persiste el paso N antes de empezar el N+1".

## N+1 y `DetachedInstanceError`

El error clásico: leer una entidad, cerrar la sesión, y luego acceder a una relación
lazy → `DetachedInstanceError`. Dos defensas:

1. **Eager load** dentro del scope con `selectinload`:

   ```python
   def get_con_items(self, invoice_id: int) -> Invoice | None:
       return self.session.execute(
           select(Invoice).where(Invoice.id == invoice_id)
           .options(selectinload(Invoice.items))
       ).scalars().first()
   ```

2. **Devolver un DTO** (no la entidad): serializa todo lo que necesitas mientras la
   sesión está abierta, y deja que la entidad muera con el scope.

Encapsula las lecturas que navegan un grafo en un método (auto_session) que carga con
`selectinload` y devuelve el DTO — así la entidad nunca "escapa" del scope.

## Resumen del flujo

```
Controller
  → Service (@transactional: abre sesión, commitea/rollback)
      → Repository (get/add/query: se une a la transacción)
          → SQLAlchemy (SessionLocal sobre el engine; zona fijada por conexión)
  → Controller convierte a DTO (dentro del scope) → JSON
```

Volver al [índice](README.md).
