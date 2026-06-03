"""Observers del demo (Listeners 1:N). Se auto-registran al importarse (`import_all_observers`
en el arranque) y los dispara `Events.dispatch(...)`. Transporte adaptativo: corren en el worker
si hay broker, si no síncrono — sin que el observer lo sepa."""
