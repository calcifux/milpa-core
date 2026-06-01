"""Jobs del módulo Example (tasks de Celery que corren en el WORKER, no en el request).

Se auto-registran: `Registry.import_all_tasks()` escanea `Modules/<X>/Jobs/` con pkgutil
e importa cada archivo, así sus `@celery_app.task` quedan registrados. Crea un archivo
con tu task y se descubre solo. Los disparas desde un controller con `.delay()`.
"""
