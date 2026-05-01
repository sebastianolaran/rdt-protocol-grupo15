# rdt-protocol-grupo15

Implementación de un protocolo de transferencia de archivos confiable sobre UDP, con soporte para **Stop and Wait** y **Selective Repeat**.

---

## Uso

Todos los comandos se ejecutan desde el directorio `src/`.

### Levantar el servidor (puerto 6666)

```bash
python3 start-server -H 127.0.0.1 -p 6666 -s storage/
```

| Flag | Descripción |
|------|-------------|
| `-H` / `--host` | IP donde escucha el servidor (default: `127.0.0.1`) |
| `-p` / `--port` | Puerto del servidor |
| `-s` / `--storage` | Directorio donde se almacenan los archivos |
| `-v` / `-q` | Verbose / Quiet |

---

### Upload

Sube un archivo local al servidor.

```bash
python3 upload -H 127.0.0.1 -p 6666 -s /ruta/al/archivo.txt -n archivo.txt
```

Con **Selective Repeat**:

```bash
python3 upload -H 127.0.0.1 -p 6666 -s /ruta/al/archivo.txt -n archivo.txt -r SelectiveRepeat
```

| Flag | Descripción |
|------|-------------|
| `-H` / `--host` | IP del servidor (default: `127.0.0.1`) |
| `-p` / `--port` | Puerto del servidor |
| `-s` / `--src` | Ruta local del archivo a subir |
| `-n` / `--name` | Nombre con el que se guardará en el servidor |
| `-r` / `--protocol` | `StopAndWait` (default) o `SelectiveRepeat` |
| `-v` / `-q` | Verbose / Quiet |

---

### Download

Descarga un archivo desde el servidor.

```bash
python3 download -H 127.0.0.1 -p 6666 -d /ruta/destino/archivo.txt -n archivo.txt
```

Con **Selective Repeat**:

```bash
python3 download -H 127.0.0.1 -p 6666 -d /ruta/destino/archivo.txt -n archivo.txt -r SelectiveRepeat
```

| Flag | Descripción |
|------|-------------|
| `-H` / `--host` | IP del servidor (default: `127.0.0.1`) |
| `-p` / `--port` | Puerto del servidor |
| `-d` / `--dst` | Ruta local donde se guardará el archivo descargado |
| `-n` / `--name` | Nombre del archivo en el servidor |
| `-r` / `--protocol` | `StopAndWait` (default) o `SelectiveRepeat` |
| `-v` / `-q` | Verbose / Quiet |
