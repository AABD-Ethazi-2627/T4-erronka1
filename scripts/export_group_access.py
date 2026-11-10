"""Export only public CA and connection instructions for the project group."""
import hashlib
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import security


def main():
    lan = security.lan_settings()
    if not lan:
        raise RuntimeError("Configure LAN access first")
    address = lan["ip"]
    certificate = (security.ROOT / "config/ca.crt").read_bytes()
    digest = hashlib.sha256(certificate).hexdigest().upper()
    readme = f"""# Acceso del grupo a CNC Guard

Conectate desde la red {lan['subnet']}.

| Servicio | URL | Autenticacion |
|---|---|---|
| Kibana | https://{address}:5601 | cncviewer y la contrasena facilitada por el responsable |
| NiFi | https://{address}:8443/nifi/ | Usuario facilitado por el responsable y contrasena propia de NiFi |
| Elasticsearch | https://{address}:9200 | cncviewer y la misma contrasena de Kibana |
| API / Swagger | https://{address}:8000/docs | Authorize: pega solo el token de la API |

## Instalar la CA publica en Windows (una vez por usuario/equipo)

1. Extrae los dos archivos de este ZIP en una carpeta.
2. Abre PowerShell en esa carpeta y comprueba el hash del certificado:

```powershell
Get-FileHash .\\ca.crt -Algorithm SHA256
```

El hash debe coincidir con el confirmado por el responsable del servidor:

`{digest}`

3. Importa la CA en el almacen de confianza de tu usuario Windows:

```powershell
certutil.exe -user -addstore Root .\\ca.crt
```

Si Windows pide confirmacion, comprueba el nombre CNC Guard Local CA antes de
aceptar. En Firefox u otros navegadores con almacen propio, importa la CA
tambien en su almacen de autoridades. Reabre el navegador si conserva el aviso.

Usa siempre HTTPS y exactamente la IP indicada. No desactives TLS.

## Credenciales y API

Solicita al responsable las credenciales por un canal privado. Este paquete
no contiene contrasenas ni tokens. Para llamar a /predict envia:

```http
Authorization: Bearer <token>
Content-Type: application/json
```

En Swagger, Authorize recibe solo el token, sin escribir el prefijo Bearer.
Elasticsearch muestra JSON; la interfaz grafica para explorar datos es Kibana.
Kibana usa un usuario de lectura; los cambios de dashboards requieren una
cuenta con permisos de edicion.

No necesitas Python, Docker, SOPS ni la clave age en los equipos del grupo.
La clave privada de age y los archivos secrets permanecen en el servidor.
"""
    destination = security.ROOT / "output/acceso-grupo.zip"
    destination.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("ca.crt", certificate)
        archive.writestr("LEEME.md", readme.encode("utf-8"))
    with zipfile.ZipFile(destination) as archive:
        if set(archive.namelist()) != {"ca.crt", "LEEME.md"}:
            raise RuntimeError("Unexpected archive content")
    print("Exported output/acceso-grupo.zip: public ca.crt and LEEME.md only.")


if __name__ == "__main__":
    main()
