# Limpieza de registros marcados como ausentes

`core.cleanup_missing` simula por defecto. No escanea E:, no comprueba existencia
actual en disco ni cambia multimedia. Solo considera `archivos.existe=0`: esa
marca procede de la ultima sincronizacion y puede estar desactualizada. No
ejecutar scanner o sync_files para esta limpieza. Revisar la marca antes de aplicar.

Protege registros relacionados por cualquier columna `archivo_id` o clave foranea
declarada hacia `archivos.id`, incluidas tablas antiguas sin restricciones. No
borra transcripciones, estados, hallazgos, hashes de registros protegidos ni rutas
activas. Ante una relacion declarada hacia otra columna, aborta por seguridad.

Desde CMD, simulacion:

```cmd
cd /d C:\vvasquez\hnoJoel\ArchivistaIA
.venv\Scripts\python.exe -B -m core.cleanup_missing
```

Para aplicar, una vez revisada la simulacion:

```cmd
.venv\Scripts\python.exe -B -m core.cleanup_missing --apply
```

Antes de borrar crea un backup consistente verificado con quick_check y un
archivo JSONL con todas las columnas de las filas retiradas, en data/backups.
Recalcula candidatos y relaciones dentro de BEGIN IMMEDIATE; el borrado se
confirma en una sola transaccion. No cambia el esquema. La transaccion puede
esperar hasta 15 segundos si otro escritor esta guardando; preferir ejecutarlo
cuando MEDIUM no este confirmando resultados. Una falla revierte el borrado;
pueden quedar backup/archivo de auditoria sin que se haya aplicado la limpieza.

Los registros retirados se conservan en backup y auditoria para mantener su
historia. No ejecutar repetidamente para actualizar la marca de existencia:
este modulo no detecta archivos borrados desde la ultima sincronizacion.

## Limpieza aplicada el 2026-10-19

Ejecucion solicitada expresamente por el usuario:

```cmd
.venv\Scripts\python.exe -X utf8 -B -u -m core.cleanup_missing --apply
```

- Antes: 339.992 registros; 1.700 con `existe=0` y 338.292 con `existe=1`.
- Seleccion recalculada: 1.700 elegibles, ninguno protegido por referencias.
- Eliminados: 1.700 registros del catalogo. Despues: 338.292, todos `existe=1`.
- Backup consistente verificado con `quick_check` antes del borrado.
- Auditoria JSONL verificada: 1.700 filas con todas sus columnas.
- `foreign_key_check` posterior: ninguna infraccion.
- No se modifico E: ni se eliminaron transcripciones o resultados relacionados.

Archivos de recuperacion, relativos a la raiz del proyecto:

- `data/backups/archivista_before_cleanup_20261019_092447_922889.db`
- `data/backups/archivista_before_cleanup_20261019_092447_922889.removed.jsonl`

La operacion tardo varios minutos. Las comprobaciones de claves foraneas pueden
recorrer tablas grandes sin indices sobre `archivo_id`. La transaccion de
borrado puede bloquear otros escritores mientras dura: que no haya una espera
inicial no significa que su duracion este limitada a 15 segundos. La transcripcion
continuo y se verifico actividad posterior en el log.

Prueba: `tests/test_cleanup_missing.py`, aprobada con una base aislada. Verifica
simulacion, proteccion de relaciones declaradas y de `archivo_id` sin FK, backup,
auditoria, conservacion de activos y ausencia de referencias rotas al aplicar.
