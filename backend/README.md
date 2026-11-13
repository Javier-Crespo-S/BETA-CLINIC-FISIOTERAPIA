# Backend de BETA CLINIC

API inicial construida con Flask. La configuración de PostgreSQL se lee de la
variable de entorno `DATABASE_URL`; la base de datos local prevista se llama
`beta_clinic_dev`.

## Requisitos

- Windows con PowerShell.
- Python 3.14.
- PostgreSQL local, con la base de datos `beta_clinic_dev` creada.

## Preparar el entorno

Desde la carpeta `backend`:

```powershell
py -3.14 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Si PowerShell no permite activar el entorno, se puede invocar directamente
`.\venv\Scripts\python.exe` en los comandos siguientes.

## Configurar y arrancar

La aplicación carga automáticamente `backend\.env` al arrancar. Para crear el
archivo local a partir de la plantilla, desde la carpeta `backend`:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Edita `.env` en tu equipo para configurar la variable `DATABASE_URL`. El archivo
`.env` está excluido del control de versiones; no compartas ni subas sus valores.
Una variable `DATABASE_URL` definida previamente en el entorno tiene prioridad
sobre la del archivo.

Arranca la aplicación desde la carpeta `backend`:

```powershell
python run.py
```

## Preparar el esquema y cargar datos ficticios

Antes de cargar el profesional de prueba, crea o actualiza las tablas aplicando
las migraciones desde la carpeta `backend`:

```powershell
python -m flask --app run db upgrade
python -m scripts.cargar_datos_prueba
```

El script utiliza la base configurada para la aplicación y solo carga datos
ficticios.

## Ejecutar las pruebas

Las pruebas exigen una base PostgreSQL aparte cuya URL se configura mediante
`TEST_DATABASE_URL`. Su nombre debe terminar en `_test`; las pruebas abortan
antes de conectarse si falta esa variable o el nombre no es válido. No utilizan
`DATABASE_URL`. La base debe existir y permitir instalar la extensión
`btree_gist`, necesaria para probar la migración.

Desde PowerShell, con el entorno virtual activado, define la URL de tu base de
pruebas y ejecuta:

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://usuario:contraseña@localhost/beta_clinic_test"
python -m pytest
```

La suite aplica las migraciones a esa base antes de ejecutar los casos. No
configures `TEST_DATABASE_URL` para apuntar a la base de desarrollo.

## Comprobar la API y PostgreSQL

Con la aplicación arrancada, en otra sesión de PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/salud
```

Si PostgreSQL responde y las credenciales son válidas, la ruta devuelve
`{"estado":"ok","base_de_datos":"conectada"}`. Si no se puede conectar,
devuelve un JSON neutro con el estado HTTP 503. La comprobación ejecuta `SELECT
1` y no crea ni modifica tablas.
