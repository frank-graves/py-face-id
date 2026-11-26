# Sistema de Control de Acceso Biométrico Facial: Un Enfoque Local-First

**Autor:** [Tu Nombre]
**Institución:** [Tu Institución]
**Fecha:** 25 de noviembre de 2026

---

## Resumen

El presente documento describe el diseño e implementación de un sistema de control de acceso biométrico facial desarrollado en Python, utilizando OpenCV para la captura y detección de rostros, DeepFace con el modelo Facenet512 para la generación de embeddings, y SQLite como base de datos local. El sistema permite registrar usuarios en caliente y verificar su identidad en tiempo real, registrando cada intento de acceso tanto localmente como —de forma opcional y asíncrona— en Firestore. La filosofía que guió el desarrollo es *Local-first*: la información sensible nunca depende de la nube para funcionar, y cualquier sincronización remota es un extra, no un requisito. Se priorizó la simplicidad, la transparencia del código y la honestidad respecto a las limitaciones del MVP, dentro de una restricción de tiempo de pocas horas y hardware sin GPU.

---

## Introducción

Los sistemas de control de acceso tradicionales —tarjetas, contraseñas, PINs— comparten una debilidad fundamental: pueden ser transferidos, prestados o robados. La biometría facial surge como una alternativa atractiva porque el "token" es inherente a la persona. Sin embargo, la mayoría de las soluciones comerciales dependen de servicios en la nube, lo cual introduce tres problemas: latencia (cada verificación requiere conexión a internet), costo (APIs por uso) y, sobre todo, privacidad (los rostros de los usuarios terminan almacenados en servidores de terceros).

Este proyecto parte de una premisa distinta: **la nube no debe ser la fuente de verdad de los datos biométricos**. Un sistema de control de acceso debe funcionar aunque se caiga la conexión, y los embeddings faciales —que son datos sensibles— deben residir, por defecto, en el disco del operador. La sincronización con servicios externos, cuando exista, debe ser explícita, optativa y tolerante a fallos.

---

## Marco Teórico

El sistema se construye sobre tres pilares técnicos.

**OpenCV** es una biblioteca de visión por computadora de código abierto ampliamente utilizada. Para este proyecto se emplea su clasificador Haar en cascada (`haarcascade_frontalface_default.xml`), que permite detectar rostros en tiempo real con CPU. Aunque existen métodos más modernos (como YuNet o MTCNN), el clasificador Haar está incluido en el paquete estándar de OpenCV, lo que evita dependencias adicionales y descargas en tiempo de ejecución —una decisión pragmática dado el contexto del MVP.

**DeepFace** es un framework de reconocimiento facial que unifica múltiples modelos preentrenados. Se eligió el modelo **Facenet512**, que produce embeddings de 512 dimensiones a partir de un rostro recortado. Estos vectores permiten comparar identidades mediante similitud coseno: dos imágenes de la misma persona producen vectores con alta similitud, mientras que dos personas distintas producen vectores con baja similitud. DeepFace abstrae la complejidad de cargar TensorFlow y ejecutar inferencia, lo que resulta ideal para un MVP.

**SQLite** es un motor de base de datos relacional embebido, sin servidor, que almacena toda la información en un único archivo. Su naturaleza local y transaccional lo convierte en el candidato natural para actuar como fuente de verdad del sistema, cumpliendo con el principio *local-first*.

---

## Proceso de Desarrollo

### Arquitectura de la solución

La arquitectura sigue un flujo lineal con dos puntos de persistencia:

```text
[Camara] -> [Detector Haar] -> [Embedder Facenet512] -> [Matcher coseno]
                                                              |
                                                              v
                                                       [SQLite local]
                                                              |
                                                              v
                                                    [Sync -> Firestore]
```

SQLite actúa como **fuente de verdad**: cada evento (acceso concedido o denegado) se escribe primero en local. Firestore actúa como **sink asíncrono**: recibe una copia best-effort del evento si (a) el operador habilitó la sincronización en `config/settings.json`, y (b) existe la credencial `serviceAccountKey.json`. Si Firestore falla —por red, por credenciales vencidas, por cuota— la aplicación no se detiene: registra una advertencia en consola y continúa operando con la copia local intacta.

Esta separación de responsabilidades fue la decisión arquitectónica más importante del proyecto. Un sistema de control de acceso que dependa de la nube para decidir si abre una puerta es, a mi juicio, un sistema mal diseñado: la disponibilidad del servicio externo se convierte en una dependencia de seguridad física.

### Toma de decisiones (ADR resumidos)

**¿Por qué Python?** Porque el ecosistema de visión por computadora está maduro en este lenguaje (OpenCV, DeepFace, NumPy), porque el autor ya tenía familiaridad con él, y porque el objetivo era demostrar el concepto funcionando en pocas horas, no optimizar el consumo de CPU. Un lenguaje compilado habría implicado resolver dependencias nativas de TensorFlow, algo desproporcionado para el contexto.

**¿Por qué se descartó PyQt en favor de la ventana nativa de OpenCV?** El alcance inicial consideraba una interfaz gráfica construida con PyQt. Se descartó por tres razones: (1) agregar PyQt implica una dependencia pesada (~60 MB) cuya instalación y empaquetado consumiría tiempo valioso; (2) la ventana nativa de OpenCV (`cv2.imshow`) permite dibujar rectángulos sobre el video y capturar eventos de teclado de forma inmediata, lo cual cubre el caso de uso; (3) la interfaz de usuario no era el objetivo del proyecto, sino un medio para interactuar con el modelo. La lección: en un MVP con deadline ajustado, la herramienta más simple que cumpla el requisito gana.

**¿Por qué un solo archivo `src/app.py`?** La tentación inicial era dividir el código en módulos (`db.py`, `firebase_logger.py`, `detector.py`, `embeddings.py`). Sin embargo, tras un primer intento de estructura modular, se detectó que el costo de mantener imports entre módulos —y de depurar problemas de `PYTHONPATH` en Windows— superaba el beneficio durante una fase de prototipado. Se consolidó todo en un archivo autocontenido con funciones claramente separadas. La modularización queda como deuda técnica explícita para una siguiente fase.

### Resolución de problemas reales

Durante la instalación de dependencias surgió un bug que vale la pena documentar porque refleja el tipo de problemas que aparecen al trabajar con paquetes de visión por computadora en Windows. Inicialmente, `pip` instaló `opencv-python-headless` como dependencia transitiva de DeepFace. Esta variante de OpenCV está compilada sin soporte para interfaz gráfica, de modo que `cv2.imshow()` lanzaba una excepción críptica al invocarse. La solución fue reinstalar explícitamente `opencv-python` (la variante con GUI) y asegurarse de que ambas versiones no coexistieran. Este incidente motivó la fijación estricta de versiones en `requirements.txt` para garantizar reproducibilidad del entorno.

Otro problema encontrado fue el comportamiento de `DeepFace.represent()` cuando no hay rostro en la imagen: por defecto lanza una excepción. Se resolvió pasando `enforce_detection=False`, lo que permite obtener un embedding incluso en ausencia de detección —aunque con menor calidad—. Para mitigar falsos positivos, el sistema aplica un umbral de similitud coseno de 0.40 antes de conceder acceso: por debajo de ese valor, el veredicto es siempre "denegado", independientemente de cuál sea el usuario más parecido en la galería.

Finalmente, se optó por almacenar los 10 embeddings de registro de cada usuario y **promediarlos** al momento de la verificación. El promedio reduce el ruido de capturas individuales (parpadeos, ángulos leves, iluminación variable) sin necesidad de algoritmos más complejos. El vector resultante se normaliza a longitud unitaria para que la similitud coseno se reduzca a un producto punto.

---

## Resultados Esperados

Al ejecutar `python -m src.app` y colocar un rostro frente a la cámara, el sistema muestra una ventana con el video en vivo, un rectángulo verde alrededor del rostro detectado y las instrucciones de uso en la parte superior. Al presionar `V` (verificar), el sistema captura el frame, calcula su embedding, lo compara contra todos los usuarios registrados y muestra el resultado durante tres segundos: fondo verde con el texto "ACCESO CONCEDIDO: <nombre>" si la similitud supera el umbral, o fondo rojo con "ACCESO DENEGADO" en caso contrario.

Cada verificación se registra en la tabla `events` de `data.db`, con los campos `id`, `ts`, `user`, `tipo`, `veredicto` y `score`. Si el operador habilitó `sync_enabled: true` en `config/settings.json` y colocó el archivo `serviceAccountKey.json` en `config/`, el evento también se replica en la colección `events` de Firestore, consultable desde la consola web de Firebase. En caso de fallo remoto, el sistema no se interrumpe: la decisión de acceso se toma sobre los datos locales.

El modo registro (`R` o `--register <nombre>`) captura 10 fotos guiadas por el operador y guarda el conjunto de embeddings en `dataset_rostros/<nombre>/embeddings.npy`, permitiendo agregar usuarios nuevos en caliente, sin reentrenamiento ni reinicio del sistema.

---

## Conclusiones y Deuda Técnica

El proyecto cumple el objetivo de demostrar un control de acceso biométrico funcional, con una arquitectura honesta respecto a sus límites. La filosofía *local-first* no es un slogan: se materializa en la elección de SQLite como fuente de verdad, en la tolerancia a fallos de la sincronización remota y en la ausencia total de dependencias obligatorias de la nube para operar.

Dicho esto, es importante ser transparente sobre lo que el sistema **no** hace:

- **No implementa anti-spoofing.** Una fotografía impresa del usuario legítimo probablemente supere la verificación. Esto es aceptable en un contexto académico, pero sería inadmisible en producción. La solución técnica pasaría por detección de *liveness* (parpadeo, profundidad, textura de piel).
- **La credencial de Firebase es estática y de larga vida.** El archivo `serviceAccountKey.json` otorga acceso total al proyecto Firebase. Si se filtra, debe rotarse manualmente. Un sistema en producción usaría credenciales de corta duración emitidas por un backend intermediario, o Workload Identity Federation.
- **No hay empaquetado como ejecutable (.exe).** La distribución actual requiere que el usuario tenga Python 3.11 instalado y ejecute el script mediante el entorno virtual. Un empaquetado con PyInstaller quedó fuera del alcance por limitaciones de tiempo.
- **Sin tests unitarios.** Solo existe un *smoke test* que valida que las dependencias se importan y que SQLite y Firestore responden. La lógica de matching, la detección y el cálculo de embeddings carecen de cobertura automatizada.
- **Un solo archivo monolítico.** La modularización propuesta en la fase de diseño (`src/db.py`, `src/detector.py`, etc.) se abandonó por pragmatismo. Refactorizar sería el primer paso de una fase 2.

Estas omisiones no son accidentes: son deuda técnica asumida conscientemente en función de un deadline ajustado y de una prioridad explícita por la funcionalidad demostrable sobre la robustez productiva.

---

## Referencias

Bradski, G. (2000). The OpenCV Library. *Dr. Dobb's Journal of Software Tools*. Documentación oficial disponible en https://docs.opencv.org/

Serengil, S. I., & Ozpinar, A. (2021). HyperExtended LightFace: A Facial Attribute Analysis Framework. *2021 International Conference on Engineering and Emerging Technologies (ICEET)*. Documentación de DeepFace disponible en https://github.com/serengil/deepface

Google. (2024). *Firebase Admin SDK — Documentación oficial*. https://firebase.google.com/docs/admin/setup

SQLite Consortium. (2024). *SQLite Documentation*. https://www.sqlite.org/docs.html