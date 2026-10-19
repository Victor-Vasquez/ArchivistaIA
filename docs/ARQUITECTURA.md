# Arquitectura actual de ArchivistaIA

Actualizado el 2026-10-19. Aplicacion local de consola para catalogar archivos,
transcribir multimedia y buscar menciones. Python 3.12.10, SQLite y faster-whisper.
No hay interfaz implementada en `ui/`; `main.py` solo informa grupos de posibles
duplicados por tamano. Las tareas se ejecutan como modulos independientes.

## Estructura y almacenamiento

- `config/settings.py`: configuracion original de rutas y extensiones.
- `core/`: catalogacion, hashes, busqueda, transcripcion, estado y limpieza.
- `data/archivista.db`: base operativa; `data/backups/`: respaldos y auditorias.
- `logs/`: registros persistentes y resultados de pruebas de rendimiento.
- `temp/medium/`: WAV temporales exclusivos del fallback FFmpeg.
- `tests/`: pruebas aisladas del transcriptor MEDIUM y la limpieza.

E: contiene los multimedia originales y se trata como solo lectura. El trabajador
MEDIUM y la limpieza no ejecutan scanner, sync_files ni recalculan hashes.
La arquitectura antigua aun contiene scripts con esas funciones; su existencia
no significa que se esten ejecutando ni que esten autorizados en esta tarea.

## SQLite y relacion con la historia

Tablas originales conservadas: `archivos`, `transcripciones`,
`transcripciones_small`, `transcripcion_small_estado`, `deteccion_menciones`,
`deteccion_coincidencias`, `busqueda_masiva`, `hallazgos_masivos`.

MEDIUM agrega `medium_runs` (intentos y estado), `medium_segments` (todos los
segmentos del intento completo) y `medium_files` (asociacion archivo/configuracion
a intento completo). Una ruta duplicada puede compartir un intento por hash
validado sin borrar la ruta ni duplicar segmentos.

La consulta de segmentos debe pasar por `medium_files.run_id`: filtrar solamente
por `medium_segments.archivo_id` omite las asociaciones reutilizadas.
Las tablas antiguas no se han consolidado ni se mezclan silenciosamente con MEDIUM.

El catalogo efectivo tiene `hash_archivo`, no `hash`. El metodo antiguo
`Database.insert_file()` todavia intenta usar `hash`; es una incompatibilidad
pendiente y no participa en el trabajador actual. La creacion del esquema sigue
repartida entre modulos, sin una migracion central versionada.

## Procesamiento MEDIUM

`core.mass_transcribe_medium`: modelo unico por proceso, CPU INT8, dos hilos,
idioma es, beam 1, VAD activo y condition_on_previous_text=False. Selecciona
`existe=1` AUDIO/VIDEO e incluye VOB catalogados OTRO. No excluye por fecha.

Registra PROCESANDO antes de inferir y cierra la conexion. Guarda segmentos,
COMPLETADO y asociacion en una transaccion; cero segmentos cuenta como completo.
Los errores no detienen el lote. Un lock Windows impide dos trabajadores de este
modulo. Al reanudar conserva los intentos anteriores, marca los que quedaron
PROCESANDO como INTERRUMPIDO y omite las asociaciones completas de la misma clave.

Ante fallo directo usa FFmpeg para extraer audio a WAV mono 16 kHz. Solo elimina
el WAV creado por esa llamada. Tras cierre forzado puede quedar un temporal;
no hay limpieza masiva automatica. No hay servicio de arranque ni vigilancia
automatica permanente: el proceso termina al agotar el lote y no sobrevive reinicios.

## Limpieza selectiva

`core.cleanup_missing` simula por defecto. Con `--apply`, solicitud explicita y
backup previo verificado, retira solo filas `existe=0` sin referencias. Detecta
`archivo_id` incluso sin FK y relaciones declaradas hacia `archivos.id`.
Preserva filas retiradas en JSONL y respaldo. No detecta nuevas ausencias en E:.
La limpieza del 2026-10-19 retiro 1.700 filas y dejo 338.292 registros activos.

Detalles y comandos: [MEDIUM](TRANSCRIPCION_MEDIUM.md) y
[limpieza](LIMPIEZA_CATALOGO.md).
