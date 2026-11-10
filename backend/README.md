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

`.env.example` documenta las variables necesarias, pero no se carga
automáticamente. En PowerShell, establece la URL para la sesión actual antes de
arrancar la aplicación:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://USUARIO:CONTRASENA@localhost:5432/beta_clinic_dev"
python run.py
```

Sustituye `USUARIO` y `CONTRASENA` por las credenciales locales de PostgreSQL.
Si la contraseña contiene caracteres especiales de URL, deben codificarse.
No guardes credenciales reales en el repositorio.

## Comprobar la API y PostgreSQL

Con la aplicación arrancada, en otra sesión de PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/salud
```

Si PostgreSQL responde y las credenciales son válidas, la ruta devuelve
`{"estado":"ok","base_de_datos":"conectada"}`. Si no se puede conectar,
devuelve un JSON neutro con el estado HTTP 503. La comprobación ejecuta `SELECT
1` y no crea ni modifica tablas.
