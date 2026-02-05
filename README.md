# TuneladoraSSH

Herramienta en Python para crear túneles SSH (local, remoto y SOCKS) entre equipos Debian, Ubuntu o Kali ... para tus cosas ...

## Requisitos

- Python 3.8+
- OpenSSH Client instalado (comando `ssh` disponible)

En Debian/Ubuntu/Kali:

```
sudo apt update
sudo apt install -y openssh-client
```

## Uso rápido

Ejecuta el modo interactivo (recomendado):

```
python3 main.py
```

También puedes invocarlo explícitamente:

```
python3 main.py interactivo
```

### Ayuda en la terminal

En el modo interactivo puedes escribir `ayuda`, `help` o `?` en cualquier paso. El programa mostrará qué debes hacer en ese campo.

## Diferencias entre túnel local, remoto y dinámico

- **Túnel local (L)**: abre un puerto en tu equipo local y lo reenvía a un destino desde el servidor remoto. Útil para acceder a un servicio remoto como si estuviera en tu máquina.
- **Túnel remoto (R)**: abre un puerto en el servidor remoto y lo reenvía hacia un destino accesible desde tu equipo local. Útil para exponer un servicio local hacia el remoto.
- **Túnel dinámico (D / SOCKS)**: crea un proxy SOCKS local. Las conexiones se enrutan dinámicamente a través del servidor SSH sin definir un destino fijo.
	- **Cómo se usa**: configuras tu navegador, sistema o aplicación para usar un proxy SOCKS en `127.0.0.1:PUERTO` (por ejemplo, `127.0.0.1:1080`).
	- **Por qué no hay destino fijo**: el cliente (navegador/app) decide a qué host conectarse y el proxy lo envía por el túnel SSH.
	- **Ejemplo**: ejecutas `python3 main.py socks 192.168.1.10 -D 1080` y luego configuras tu navegador con proxy SOCKS5 en `127.0.0.1:1080`.

## Uso no interactivo

### Túnel local (L)

```
python3 main.py local 192.168.1.10 -L 8080:127.0.0.1:80
```

### Túnel remoto (R)

```
python3 main.py remoto 192.168.1.10 -R 9090:127.0.0.1:22
```

### SOCKS dinámico (D)

```
python3 main.py socks 192.168.1.10 -D 1080
```

## Opciones comunes

- `-L`, `--forward`: reenvío local en formato `[bind_address:]local_port:dest_host:dest_port` (solo modo `local`)
- `-R`, `--forward`: reenvío remoto en formato `[bind_address:]remote_port:dest_host:dest_port` (solo modo `remoto`)
- `-D`, `--forward`: puerto SOCKS en formato `[bind_address:]socks_port` (solo modo `socks`)
- `-u`, `--user`: usuario SSH
- `-p`, `--port`: puerto SSH
- `-i`, `--identity`: ruta a clave privada
- `--no-pty`: desactiva pseudo-TTY
- `--keepalive`: intervalo de keepalive en segundos
- `--ssh-arg`: argumentos extra para `ssh` (repetible)
- `-f`, `--background`: ejecuta en segundo plano
- `-c`, `--command`: comando remoto (si se usa, no se añade `-N`)

### Ejemplos con opciones comunes

```
python3 main.py local 192.168.1.10 -L 8080:127.0.0.1:80 -u ubuntu -p 22
python3 main.py remoto 192.168.1.10 -R 9090:127.0.0.1:22 -u root -i ~/.ssh/id_rsa
python3 main.py socks 192.168.1.10 -D 1080 --keepalive 20 --no-pty
python3 main.py local 192.168.1.10 -L 8080:127.0.0.1:80 --ssh-arg -v --ssh-arg -o --ssh-arg StrictHostKeyChecking=no
```

### ¿Se pueden combinar?

Sí. Todas las opciones comunes (`-u`, `-p`, `-i`, `--keepalive`, `--no-pty`, `--ssh-arg`, `-f`, `-c`) se pueden combinar con el modo elegido.
La única restricción es que el tipo de reenvío debe coincidir con el modo:

- Modo `local` requiere `-L`
- Modo `remoto` requiere `-R`
- Modo `socks` requiere `-D`

## Persistencia de configuración

El modo interactivo guarda la configuración en:

```
~/.config/tuneladorassh/config.json
```

Puedes borrar ese archivo si quieres reiniciar la configuración.

## Notas

- Los túneles usan el cliente OpenSSH del sistema.
- El proceso se puede detener con `Ctrl+C`.
