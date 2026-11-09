Instrucciones para Copilot: web de fisioterapia

Este archivo va en .github/copilot-instructions.md. Léelo entero antes de proponer o escribir código.

1. Contexto del proyecto

Aplicación web full-stack para una clínica de fisioterapia. Empieza con un solo profesional, pero el diseño debe permitir añadir más profesionales en el futuro sin rehacer el modelo de datos.

Funcionalidades previstas (todo el proyecto):

Web informativa: quién es el profesional, especialidad, ubicación y contacto.
Reserva de citas con agenda que impida solapamientos de horario.
Primera cita sin registro: el usuario nuevo puede reservar sin crear cuenta.
Login de pacientes con su cuenta.
Perfil del paciente: citas anteriores y próximas, ejercicios de rehabilitación con su calendarización y feedback del paciente para que el profesional haga seguimiento.
Panel del profesional: agenda diaria y semanal, ficha de paciente, asignación de ejercicios, seguimiento.
Más adelante: recordatorios automáticos, gráficas de evolución, lista de espera, pasarela de pago, bonos de sesiones y facturas en PDF.

Orden de desarrollo orientativo (a confirmar conmigo antes de empezar cada fase):

Web informativa y reserva de citas con agenda, más panel básico del profesional.
Cuentas de paciente, historial y ejercicios con feedback.
Recordatorios, gráficas de evolución y lista de espera.
Pagos, bonos y facturación.


2. Cómo debes trabajar conmigo
Explica brevemente lo que haces y por qué, y define cualquier concepto nuevo en una o dos frases.
Pide mi consentimiento antes de cambios grandes. Cuenta como cambio grande:
Crear, mover o borrar carpetas o muchos archivos a la vez.
Añadir o cambiar dependencias o herramientas.
Cambiar el esquema de la base de datos o crear migraciones.
Cambiar la autenticación, los permisos o cualquier cosa relacionada con datos de pacientes.
Refactorizar código que ya funciona.
Para cambios pequeños (corregir un error, añadir una función acotada) puedes proceder, pero resume qué has hecho.
No elijas tecnologías por mí. Si algo no está decidido en este documento, preséntame 2 o 3 opciones con ventajas e inconvenientes y espera mi respuesta.
Si no entiendes lo que pido o falta información, pregúntame en vez de suponer.
Avanza en pasos pequeños y comprobables, y dime cómo probar cada uno.


3. Idioma

Todo en español: comentarios, mensajes de commit, documentación, textos de la interfaz y mensajes de error. La web es solo en español (no hace falta internacionalización por ahora). Para nombres de variables y funciones, usa español en los conceptos del dominio (paciente, cita, ejercicio) y mantén coherencia en todo el proyecto.


4. Tecnologías

Decididas:

Capa	Tecnología
Frontend	React con JavaScript (sin TypeScript)
Backend	Python con Flask
Base de datos	PostgreSQL
Autenticación	Servicio gestionado externo (no implementar login desde cero)
Organización	Monorepo: frontend y backend separados en un mismo repositorio

Pendientes de decidir (no las elijas tú; consúltame antes):

Extensiones y librerías de Flask: acceso a base de datos (ORM), migraciones, validación de datos y verificación de los tokens del servicio de autenticación.
Herramienta de arranque y construcción del frontend, y librería de estilos.
Proveedor concreto de autenticación gestionada.
Hosting (debe estar en la UE) y base de datos gestionada.
Servicio de envío de emails y de SMS o WhatsApp.
Pasarela de pago (por ejemplo Stripe o Redsys), para la fase 4.
Herramientas de testing.


5. Estructura del repositorio

Estructura de alto nivel; la organización interna del backend (Flask) se acordará antes de crearla:

/
├── frontend/   # aplicación React
├── backend/    # API en Python
├── docs/       # decisiones y documentación del proyecto
└── .github/
    └── copilot-instructions.md
El frontend nunca accede directamente a la base de datos: siempre pasa por la API del backend.
Cada parte tiene sus propias dependencias y su propio README con instrucciones para arrancarla.
Variables de entorno de ejemplo en .env.example (sin valores reales).


6. Datos de salud y RGPD (prioridad máxima)

Aunque solo guardemos identificación básica, ejercicios, calendario y cobros, trata todo dato de paciente como dato de salud (categoría especial del RGPD y la LOPDGDD). Reglas obligatorias:

Minimización: guarda solo lo imprescindible. No añadas campos con información clínica sin consultarme. Evita campos de texto libre cuando una opción estructurada sirva (escala de dolor 0-10, "completado / no completado").
Control de acceso por roles (paciente, profesional, y en el futuro administrador). Un paciente solo ve sus propios datos. Comprueba los permisos en el backend, nunca solo en el frontend.
Cifrado en tránsito (HTTPS siempre) y en reposo.
Registro de accesos: guarda quién consulta o modifica datos de pacientes y cuándo.
Mensajes neutros: los emails, SMS o notificaciones no deben mencionar tipo de lesión, tratamiento ni ejercicios. Solo algo como "Recordatorio de tu cita el día X a las Y".
No escribir datos personales en los logs, ni en mensajes de error, ni en URLs.
Consentimientos: debe existir información clara de privacidad y consentimiento explícito donde corresponda, y guardar cuándo se aceptó.
Derechos del usuario: diseña pensando en poder exportar, rectificar y borrar los datos de un paciente.
Proveedores externos (autenticación, hosting, base de datos, email): deben estar en la UE o tener garantías equivalentes y contrato de encargado de tratamiento. Avísame antes de integrar cualquiera.
Pagos: nunca almacenar datos de tarjeta; los gestiona la pasarela.
Datos de prueba: usa siempre datos ficticios. Nunca datos reales de pacientes en desarrollo.

Recuerda que la normativa final debe validarla un especialista en protección de datos; si una decisión de diseño puede afectar al RGPD, avísame.


7. Reglas de la agenda y las citas
Evitar solapamientos garantizándolo en la base de datos (restricciones o transacciones), no solo en el frontend. Debe resistir que dos personas reserven el mismo hueco a la vez.
Duración variable según el tipo de sesión (por ejemplo valoración inicial frente a seguimiento).
Disponibilidad configurable: horarios por día, descansos, vacaciones y festivos.
Zona horaria: guarda las fechas con zona horaria (UTC) y muéstralas en hora de España peninsular, teniendo en cuenta el cambio de hora.
Reserva temporal del hueco mientras el usuario completa el formulario, con caducidad.
Cancelar y reprogramar con reglas de antelación configurables.
El modelo de datos debe permitir varios profesionales, cada uno con su agenda, aunque al principio haya uno solo.


8. Reserva sin registro
Pedir los datos mínimos de contacto y verificar el email.
La cita queda asociada a esa persona y se gestiona (consultar, cancelar) con un enlace único y no adivinable.
Ofrecer después crear la cuenta vinculando las citas previas.


9. Seguridad general
Secretos y claves siempre en variables de entorno; nunca en el código ni en el repositorio.
Validar y limpiar toda entrada del usuario en el backend.
Consultas a base de datos parametrizadas (prevenir inyección SQL).
Configurar CORS de forma restrictiva, y limitar el número de intentos en login y reservas (rate limiting).
Protección contra XSS y CSRF según el método de sesión elegido.
Respuestas de error que no revelen detalles internos.
Mantener las dependencias actualizadas y avisarme de vulnerabilidades conocidas.
No dejes endpoints de depuración ni credenciales por defecto.


10. Calidad del código
Código simple y legible antes que ingenioso. Funciones cortas con una sola responsabilidad.
Comentarios en español que expliquen el porqué, no lo obvio.
Manejo de errores explícito, con mensajes claros para el usuario.
La lógica de agenda, permisos y pagos debe tener tests. Pregúntame qué herramienta de tests usar antes de añadirla.
Interfaz móvil primero y accesible (WCAG): contraste, etiquetas en formularios, navegación por teclado.
Incluir SEO básico en la web pública (títulos, descripciones, datos estructurados de negocio local).


11. Git
Commits pequeños, en español, con mensaje que explique qué cambia y por qué.
Nunca subir archivos .env, claves ni datos reales.
No reescribir el historial ni hacer cambios masivos sin avisarme.
No inventes APIs o funciones: si no estás seguro de que existen, dímelo.