# Estado y pendientes

Actualizado el 2026-10-19. Esta lista documenta lo existente y los pendientes;
no autoriza automaticamente cambios de esquema, borrados o nuevas tareas.

## Implementado y validado

- MEDIUM reanudable, un modelo, estados por intento y todos los segmentos.
- Guardado atomico sin transaccion SQLite durante la transcripcion.
- Fallback FFmpeg mono 16 kHz y reutilizacion de duplicados por hashes almacenados.
- Log persistente, proteccion contra dos trabajadores del mismo modulo.
- CPU ajustada a dos hilos tras benchmark; prioridad operativa Normal.
- Arranque con una consulta de completados en lugar de una conexion por candidato.
- Ocho pruebas aisladas MEDIUM y prueba real de lectura directa, fallback,
  persistencia y reanudacion, documentadas en TRANSCRIPCION_MEDIUM.md.
- Limpieza selectiva con simulacion, backup, auditoria y proteccion de referencias;
  prueba aislada aprobada. Aplicada el 2026-10-19 a 1.700 registros ausentes.

## Trabajo en curso

- Completar transcripcion activa. Corte del 2026-10-19 09:31 America/Santiago:
  8.466 de 11.769 archivos resueltos (71,9%), 278.014 segmentos, 3.303 restantes
  incluidos 305 errores. Consultar --dry-run y el log para datos actuales.
- Revisar despues los archivos con error sin descartar resultados ni originales.

## Pendientes tecnicos

- Consolidar inicializacion/migraciones SQLite y corregir `hash` frente a
  `hash_archivo` en la insercion antigua.
- Evaluar indices sobre relaciones `archivo_id`: las verificaciones de borrado
  resultaron lentas. Medir y respaldar antes de cambiar el esquema.
- Disenar consolidacion futura de transcripciones manteniendo procedencia,
  modelos, configuraciones, IDs y asociaciones de duplicados.
- Definir reanudacion automatica tras reinicio y notificacion final si se solicita;
  actualmente ambas requieren intervencion y no estan implementadas.
- Completar instrucciones de proyecto: AGENTS.md sigue siendo una lista general
  de temas; no contiene el detalle operativo de estos documentos.
- Revisar y confirmar cambios en Git. En la revision de esta sesion, los tres
  archivos originales de MEDIUM estaban preparados sin commit, mientras limpieza
  y otros documentos seguian sin seguimiento. No se realizo push.

Referencias: [arquitectura](ARQUITECTURA.md),
[transcripcion MEDIUM](TRANSCRIPCION_MEDIUM.md), [limpieza](LIMPIEZA_CATALOGO.md).
