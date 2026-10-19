# Transcripcion MEDIUM reanudable

Ejecutable autorizado: `C:\vvasquez\hnoJoel\ArchivistaIA\.venv\Scripts\python.exe` (Python 3.12.10).
Modulo: `core.mass_transcribe_medium`. Ejecutar desde la raiz del proyecto.

## Estado documentado: 2026-10-19, 09:31 America/Santiago

Esta es una instantanea, no un indicador en vivo:

- Trabajador activo: PID efectivo 15420, prioridad Normal; iniciado el 2026-10-18.
- Configuracion vigente: MEDIUM, CPU INT8, **cpu_threads=2**, un solo modelo.
- Candidatos activos: 11.769; resueltos: 8.466 (71,9%).
- Resueltos: 8.395 transcripciones completas y 71 asociaciones reutilizadas.
- Segmentos persistidos: 278.014. Restantes: 3.303, incluidos 305 errores y
  el archivo en curso. Los errores se cuentan por ultimo intento de cada archivo,
  no por suma de intentos historicos.
- Archivo en curso: ID 258879, `E:\z\RMA\Victor\100_imagenes\fotos\2013\20130112_200911.mp4`.
- Catalogo tras limpieza autorizada: 338.292 registros, todos `existe=1`.
  Ver [limpieza del catalogo](LIMPIEZA_CATALOGO.md). Los candidatos activos no
  disminuyeron porque solo se retiraron filas que ya estaban marcadas ausentes.

Los PID y contadores de las secciones fechadas anteriores son historicos.
Consultar estado desde CMD sin cargar Whisper:

```cmd
cd /d C:\vvasquez\hnoJoel\ArchivistaIA
.venv\Scripts\python.exe -B -m core.mass_transcribe_medium --dry-run
```

Log en vivo desde CMD:

```cmd
powershell -NoProfile -Command "Get-Content 'C:\vvasquez\hnoJoel\ArchivistaIA\logs\mass_transcribe_medium.log' -Encoding UTF8 -Tail 15 -Wait"
```

Ctrl+C cierra el visor sin detener el trabajador. Tras reinicio del equipo hay
que reanudar explicitamente; `--dry-run` y el visor no lo arrancan.
Lanzamiento manual en primer plano, solo si no hay otro trabajador:

```cmd
.venv\Scripts\python.exe -X utf8 -B -u -m core.mass_transcribe_medium
```

Este ultimo comando depende de mantener abierta su consola. Los lanzamientos
realizados desde la sesion de trabajo usaron Start-Process con ventana oculta,
salidas adicionales con fecha y prioridad Normal. El archivo principal de log
siempre se conserva y recibe entradas nuevas.

## Alcance y datos historicos

No modifica `archivos` ni las tablas antiguas. E: solo se lee. No ejecuta scanner,
sync_files ni calcula hashes multimedia. Incluye existe=1 AUDIO/VIDEO y VOB
catalogados como OTRO (clasificados como video solo para seleccion). Sin filtro
por fecha. Un lote recorre todos los pendientes y termina; volver a lanzarlo
reanuda. Los ERROR se reintentan en la siguiente ejecucion, no infinitamente en
la misma. No instala tareas programadas ni arranca automaticamente tras reinicio.

## Esquema aditivo

- medium_runs: intento, archivo origen, modelo, configuracion JSON y clave,
  firma de tamano/mtime, hash previamente catalogado, estado, tiempos, error,
  cantidad de segmentos y modo directo/ffmpeg. Conserva intentos fallidos.
- medium_segments: todos los segmentos (incluso texto vacio), run_id, archivo_id
  origen, inicio, fin y texto.
- medium_files: relacion archivo/configuracion -> ejecucion completada; permite
  que rutas duplicadas compartan segmentos sin borrar rutas ni copiar texto.
- Indices: idx_medium_segments_run, idx_medium_runs_hash, idx_medium_files_run,
  mas el indice automatico de la clave primaria compuesta de medium_files.

Consulta de segmentos para CUALQUIER ruta, incluidas copias:

```sql
SELECT f.archivo_id, r.modelo, r.config_json, s.inicio, s.fin, s.texto
FROM medium_files f
JOIN medium_runs r ON r.id=f.run_id
JOIN medium_segments s ON s.run_id=r.id
WHERE f.archivo_id=? AND f.config_key=?
ORDER BY s.inicio, s.id;
```

Los IDs de tablas historicas y nuevas tienen espacios propios. Una futura
consolidacion debe conservar tabla de origen, configuracion y relaciones; no
suponer que todos los resultados small/medium son equivalentes.

## Modelo, transacciones y recuperacion

Whisper medium CPU int8 se carga una vez por proceso con trabajo pendiente.
Idioma es, beam_size=1, vad_filter=True, condition_on_previous_text=False.
La clave incorpora opciones, version de faster-whisper/ctranslate2 y pipeline.
Se registra PROCESANDO y se cierra SQLite ANTES de transcribir. Segmentos,
COMPLETADO y asociacion se guardan en una transaccion corta y atomica. Cero
segmentos es COMPLETADO. Un lock de Windows impide dos trabajadores de este
modulo; al reiniciar se marcan intentos PROCESANDO como INTERRUMPIDO y se crean
intentos nuevos. No se borran intentos ni segmentos.

Fallback: ante excepcion directa, FFmpeg extrae la primera pista de audio a WAV
mono PCM 16 kHz en temp/medium y reintenta con el mismo modelo. Solo elimina su
propio WAV en finally. Tras terminacion forzada puede quedar un WAV huerfano;
no hay borrado masivo automatico. FFmpeg tiene timeout de dos horas. Las
excepciones de archivos se registran y el lote continua. Errores de infraestructura
(por ejemplo disco local lleno o modelo imposible de cargar) pueden detener el
trabajador; se registran y puede reanudarse.

Duplicados: solo hashes hexadecimales de 64 caracteres, misma configuracion,
ejecucion completa y mismo tamano. Para ambas rutas se exige que tamano y mtime
actuales coincidan con el catalogo, y para el origen con la firma transcrita.
Sin recalcular contenido no es posible detectar una alteracion que conserve
exactamente tamano y mtime; los hashes validos almacenados son la fuente de
confianza. PRUEBA y hashes faltantes no se reutilizan. No se transfiere un estado
COMPLETADO entre configuraciones distintas.

## Comandos

```powershell
& '.\.venv\Scripts\python.exe' -B -m core.mass_transcribe_medium --dry-run
& '.\.venv\Scripts\python.exe' -B -m core.mass_transcribe_medium --prepare
& '.\.venv\Scripts\python.exe' -B -m core.mass_transcribe_medium --file-id 22516
& '.\.venv\Scripts\python.exe' -B -m core.mass_transcribe_medium
& '.\.venv\Scripts\python.exe' -B -m unittest discover -s tests -p test_mass_transcribe_medium.py
```

--prepare crea primero backup consistente con SQLite backup API, verifica
quick_check y despues crea el esquema. El trabajador normal requiere esquema
ya preparado. No usar --prepare simultaneamente con otro escritor externo.
--dry-run no carga Whisper. --force-fallback solo se admite con --file-id para
validacion controlada y no reprocesa completados.

Log persistente: logs/mass_transcribe_medium.log (append, UTF-8), incluye PID,
configuracion, archivo/total, ID, ruta, segmentos, modo, duracion, errores y
progreso. Heartbeat cada 45 segundos durante un archivo. Mantener el equipo
encendido; cierre de sesion o reinicio puede terminar el proceso, pero se reanuda.

## Regresion conservada

logs/homenaje_hno_joel_medium.txt es una transcripcion MEDIUM historica del
archivo ID 83826. Se preserva intacta. Alrededor de 745.2-751.2 y 755.2-760.2
contiene `pastor Sercio`. No se exige que un detector literal de Celso lo encuentre.
El TXT no registra toda la configuracion/version ni certifica por si solo la
completitud; no se importa ni se etiqueta silenciosamente como resultado de
la configuracion nueva. Sirve como referencia de regresion sin retranscribirlo
para las pruebas. La seleccion general no lo excluye por fecha o nombre.

## Validacion realizada el 2026-09-28

- Python 3.12.10, faster-whisper 1.2.1, CTranslate2 4.8.2.
- E: accesible; FFmpeg y ffprobe disponibles; sin otro trabajador Whisper al inicio.
- Sintaxis validada con ast.parse (sin crear bytecode).
- Ocho pruebas unitarias aisladas aprobadas: seleccion de VOB/antiguos,
  exclusion de inactivos, cero segmentos, reanudacion, reintento tras error,
  rollback atomico, reutilizacion por hash valido, hash invalido/metadatos
  desactualizados, archivo ausente, fallback y limpieza de WAV.
- Backup: data/backups/archivista_before_medium_20260928_232306_806094.db,
  quick_check OK antes de agregar esquema. Contenido y recuentos de las ocho
  tablas historicas comparados contra backup sin diferencias.
- Archivo controlado ID 22516, PTT-20210801-WA0009.opus, 43.222 segundos.
  Lectura directa: 13 segmentos. Fallback real: 13 segmentos, WAV verificado
  mono 16000 Hz, guardado COMPLETADO en run_id=1, sin WAV residual.
- Fue posible adquirir una transaccion de escritura independiente antes de
  consumir Whisper: el trabajador no mantenia una transaccion abierta.
- Repeticion del ID 22516 omitida sin nueva transcripcion ni nuevo intento.
- foreign_key_check sin infracciones; segmentos guardados coinciden con contador.
- Seleccion inicial: 11.769 (11.698 AUDIO/VIDEO + 71 VOB catalogados OTRO).
  Completados anteriores con esta configuracion: 0; despues de prueba: 1;
  pendientes al lanzamiento: 11.768.

Comando del lote: `C:\vvasquez\hnoJoel\ArchivistaIA\.venv\Scripts\python.exe -B -u -m core.mass_transcribe_medium`
Directorio de trabajo: `C:\vvasquez\hnoJoel\ArchivistaIA`.
Se inicia con Start-Process -WindowStyle Hidden, con stdout/stderr adicionales
 en logs/mass_transcribe_medium.stdout.log y logs/mass_transcribe_medium.stderr.log.
El PID efectivo y archivo actual se registran en mass_transcribe_medium.log.

Lote lanzado el 2026-09-28 a las 23:30 (America/Santiago).
PID del lanzador del entorno virtual: 15400. PID efectivo registrado por Python:
10476. Los procesos adicionales de VS Code y la consola Python fueron
inspeccionados: no tenian el runtime CTranslate2 cargado. No se detuvieron.

## Evaluacion de rendimiento - 2026-10-09

Equipo: Intel Core i7-6600U, 2 nucleos fisicos / 4 hilos logicos, aproximadamente
8 GB RAM. Consulta inicial: aproximadamente 3 GB RAM fisica disponible.
El trabajador usa MEDIUM CPU INT8, beam_size=1, un modelo y num_workers=1.
faster-whisper 1.2.1 documenta cuatro hilos CPU predeterminados; no se especifica
cpu_threads en el trabajador. Prioridad observada: High. Plan de energia actual
permite maximo CPU 100% tanto conectado como con bateria, refrigeracion activa
con corriente alterna. No se cambio el plan ni la prioridad.

Medicion no invasiva del PID 17520: 35.75 segundos CPU en 10.214 segundos de
reloj, equivalente a 87.5% de los cuatro hilos logicos. Es una muestra puntual,
no un benchmark de transcripcion. Sugiere poco margen de CPU ociosa; no demuestra
que mas hilos ni mas procesos mejoren el rendimiento. Contadores WMI adicionales
de frecuencia/entrada de paginas no estuvieron disponibles, por lo que no se
certifica ausencia de limitacion termica ni de paginacion.

No se lanzo otra instancia Whisper ni se interrumpio el lote para benchmarks.
No se cambio configuracion de inferencia ni clave de reanudacion. Comparar dos
contra cuatro hilos o probar BatchedInferencePipeline requiere un benchmark
controlado sin competencia del trabajador activo. Cambiar pipeline puede alterar
segmentacion/resultados: no reutilizar silenciosamente una clave de configuracion
existente, ni invalidar completados y reprocesar toda la coleccion.

## Optimizacion medida - 2026-10-10

Tras reinicio, sin otro transcriptor, benchmark secuencial de MEDIUM CPU INT8
con la misma muestra de 20 segundos del archivo 22516 y las mismas opciones.
Cada modelo hizo calentamiento de tres segundos antes de medir. Dos hilos:
18.855 s; cuatro hilos: 24.117 s. Ambos devolvieron seis segmentos y exactamente
el mismo texto. Resultado en logs/medium_cpu_benchmark.json. Una sola muestra:
reduccion de tiempo del 21.8%, no garantia para todos los archivos.

Se establece cpu_threads=2 y se reinicia con prioridad Normal, buscando mejor
respuesta de Windows tras el bloqueo reportado. No se atribuye la causa del
bloqueo exclusivamente a High. No se modifica modelo MEDIUM, INT8, idioma,
beam_size, VAD ni condition_on_previous_text. Los hilos son un ajuste de ejecucion;
se registran en el log y se conserva la clave de opciones de transcripcion para
no repetir los resultados completos. No se habilita batching ni otro pipeline.

Arranque optimizado: IDs completos consultados una vez con un JOIN en lugar de
abrir SQLite por cada candidato. El control por archivo y la reutilizacion por
hash siguen presentes. No cambia esquema ni tablas historicas.
