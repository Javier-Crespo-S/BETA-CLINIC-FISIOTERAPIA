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

## Comprobar la API y PostgreSQL

Con la aplicación arrancada, en otra sesión de PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/salud
```

Si PostgreSQL responde y las credenciales son válidas, la ruta devuelve
`{"estado":"ok","base_de_datos":"conectada"}`. Si no se puede conectar,
devuelve un JSON neutro con el estado HTTP 503. La comprobación ejecuta `SELECT
1` y no crea ni modifica tablas.
