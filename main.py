#!/usr/bin/env python3
"""Gestor simple de túneles SSH.

Soporta:
  - Reenvío local (L)
  - Reenvío remoto (R)
  - SOCKS dinámico (D)

Requisitos:
  - Paquete OpenSSH Client instalado (comando ssh disponible)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ConfigTunel:
	# Configuración base del túnel
	usuario: Optional[str]
	host: str
	puerto: int
	archivo_identidad: Optional[str]
	sin_pty: bool
	keepalive: int
	args_ssh_extra: List[str]

	def destino(self) -> str:
		# Devuelve la cadena user@host o solo host si no hay usuario
		if self.usuario:
			return f"{self.usuario}@{self.host}"
		return self.host


def _requerir_ssh() -> None:
	# Verifica que el cliente SSH esté disponible
	if shutil.which("ssh") is None:
		print("Error: no tienes instalado OpenSSH o no se encontró el comando 'ssh'. Instala 'openssh-client'.", file=sys.stderr)
		sys.exit(1)


def _obtener_ruta_config() -> str:
	# Ruta estándar en ~/.config/tunelssh/config.json
	base = os.path.join(os.path.expanduser("~"), ".config", "tuneladorassh")
	return os.path.join(base, "config.json")


def _cargar_config() -> Dict[str, Any]:
	# Carga configuración persistente si existe
	ruta = _obtener_ruta_config()
	if not os.path.exists(ruta):
		return {}
	try:
		with open(ruta, "r", encoding="utf-8") as archivo:
			return json.load(archivo)
	except (OSError, json.JSONDecodeError):
		return {}


def _guardar_config(datos: Dict[str, Any]) -> None:
	# Guarda configuración persistente en disco
	ruta = _obtener_ruta_config()
	os.makedirs(os.path.dirname(ruta), exist_ok=True)
	with open(ruta, "w", encoding="utf-8") as archivo:
		json.dump(datos, archivo, ensure_ascii=False, indent=2)


def _obtener_entero_config(valor: Any, defecto: int) -> int:
	# Convierte un valor de configuración a entero 
	if isinstance(valor, int):
		return valor
	if isinstance(valor, str):
		texto = valor.strip()
		if texto.isdigit():
			return int(texto)
	return defecto


def _construir_args_ssh_base(cfg: ConfigTunel) -> List[str]:
	# Construye los argumentos base para el comando ssh
	args = ["ssh"]

	if cfg.sin_pty:
		args.append("-T")

	args += [
		"-o",
		"ExitOnForwardFailure=yes",
		"-o",
		f"ServerAliveInterval={cfg.keepalive}",
		"-o",
		"ServerAliveCountMax=3",
	]

	if cfg.archivo_identidad:
		args += ["-i", cfg.archivo_identidad]

	if cfg.puerto != 22:
		args += ["-p", str(cfg.puerto)]

	if cfg.args_ssh_extra:
		args += cfg.args_ssh_extra

	return args


def _ejecutar_ssh(args: List[str]) -> int:
	# Ejecuta el comando ssh y reenvía señales
	try:
		proc = subprocess.Popen(args)
	except FileNotFoundError:
		print("Error: no se pudo ejecutar 'ssh'.", file=sys.stderr)
		return 1

	def _manejar_senal(signo: int, _frame) -> None:
		try:
			proc.send_signal(signo)
		except ProcessLookupError:
			return

	signal.signal(signal.SIGINT, _manejar_senal)
	signal.signal(signal.SIGTERM, _manejar_senal)

	return proc.wait()


def _validar_reenvio_local(valor: str) -> str:
	# Formato: [bind_address:]local_port:dest_host:dest_port
	partes = valor.split(":")
	if len(partes) not in (3, 4):
		raise argparse.ArgumentTypeError(
			"Formato inválido. Deberías utilizar algo como: [bind_address:]local_port:dest_host:dest_port"
		)
	return valor


def _validar_reenvio_remoto(valor: str) -> str:
	# Formato: [bind_address:]remote_port:dest_host:dest_port
	partes = valor.split(":")
	if len(partes) not in (3, 4):
		raise argparse.ArgumentTypeError(
			"Formato inválido. Deberías utilizar algo como: [bind_address:]remote_port:dest_host:dest_port"
		)
	return valor


def _validar_socks(valor: str) -> str:
	# Formato: [bind_address:]socks_port
	partes = valor.split(":")
	if len(partes) not in (1, 2):
		raise argparse.ArgumentTypeError("Formato inválido. Deberías utilizar algo como: [bind_address:]socks_port")
	return valor


def _es_solicitud_ayuda(entrada: str) -> bool:
	# Detecta si el usuario pidió ayuda
	return entrada.strip().lower() in {"ayuda", "help", "?"}


def _pedir_texto(
	etiqueta: str,
	defecto: Optional[str] = None,
	obligatorio: bool = False,
	ayuda_texto: Optional[str] = None,
) -> str:
	# Solicita texto por consola con valor por defecto
	while True:
		if defecto:
			entrada = input(f"{etiqueta} [{defecto}]: ").strip()
			if _es_solicitud_ayuda(entrada):
				print(ayuda_texto or "Escribe el valor solicitado o deja vacío para usar el valor por defecto.")
				continue
			if entrada:
				return entrada
			if defecto:
				return defecto
		else:
			entrada = input(f"{etiqueta}: ").strip()
			if _es_solicitud_ayuda(entrada):
				print(ayuda_texto or "Escribe el valor solicitado.")
				continue
			if entrada or not obligatorio:
				return entrada
		print("Este campo es obligatorio. Debes indicar un valor válido.")


def _pedir_entero(etiqueta: str, defecto: int, ayuda_texto: Optional[str] = None) -> int:
	# Solicita un entero por consola con valor por defecto
	while True:
		entrada = input(f"{etiqueta} [{defecto}]: ").strip()
		if _es_solicitud_ayuda(entrada):
			print(ayuda_texto or "Introduce un número entero. Si dejas vacío, se usa el valor por defecto.")
			continue
		if not entrada:
			return defecto
		try:
			return int(entrada)
		except ValueError:
			print("Valor inválido. Debe ser un número entero.")


def _pedir_si_no(etiqueta: str, defecto: bool, ayuda_texto: Optional[str] = None) -> bool:
	# Solicita un sí/no por consola
	valor_defecto = "s" if defecto else "n"
	while True:
		entrada = input(f"{etiqueta} [s/n] ({valor_defecto}): ").strip().lower()
		if _es_solicitud_ayuda(entrada):
			print(ayuda_texto or "Responde con s o n. Si dejas vacío, se usa el valor por defecto.")
			continue
		if not entrada:
			return defecto
		if entrada in ("s", "si", "sí"):
			return True
		if entrada in ("n", "no"):
			return False
		print("Respuesta inválida. Usa s o n.")


def _pedir_lista(etiqueta: str, defecto: List[str], ayuda_texto: Optional[str] = None) -> List[str]:
	# Solicita una lista separada por comas
	texto_defecto = ",".join(defecto) if defecto else ""
	entrada = input(f"{etiqueta} [{texto_defecto}]: ").strip()
	if _es_solicitud_ayuda(entrada):
		print(ayuda_texto or "Introduce valores separados por comas o deja vacío para usar el valor por defecto.")
		return _pedir_lista(etiqueta, defecto, ayuda_texto)
	if not entrada:
		return defecto
	return [item.strip() for item in entrada.split(",") if item.strip()]


def _pedir_reenvio(modo: str, defecto: str) -> str:
	# Valida el formato del reenvío según el modo
	if modo == "local":
		ayuda_reenvio = "Ejemplo local: 8080:127.0.0.1:80 o 0.0.0.0:8080:127.0.0.1:80"
	elif modo == "remoto":
		ayuda_reenvio = "Ejemplo remoto: 9090:127.0.0.1:22"
	else:
		ayuda_reenvio = "Ejemplo socks: 1080 o 127.0.0.1:1080"
	while True:
		entrada = _pedir_texto("Reenvío", defecto=defecto, obligatorio=True, ayuda_texto=ayuda_reenvio)
		try:
			if modo == "local":
				return _validar_reenvio_local(entrada)
			if modo == "remoto":
				return _validar_reenvio_remoto(entrada)
			if modo == "socks":
				return _validar_socks(entrada)
		except argparse.ArgumentTypeError as exc:
			print(str(exc))


def _construir_parser() -> argparse.ArgumentParser:
	# Parser de línea de comandos (modo no interactivo)
	parser = argparse.ArgumentParser(
		prog="tunelssh",
		description="TuneladoraSSH (local, remoto y dinámico).",
		formatter_class=argparse.ArgumentDefaultsHelpFormatter,
	)

	parser.add_argument("--user", "-u", help="Usuario SSH")
	parser.add_argument("--port", "-p", type=int, default=22, help="Puerto SSH")
	parser.add_argument("--identity", "-i", help="Ruta a clave privada")
	parser.add_argument("--no-pty", action="store_true", help="Desactiva pseudo-TTY")
	parser.add_argument(
		"--keepalive",
		type=int,
		default=30,
		help="Intervalo de keepalive (segundos)",
	)
	parser.add_argument(
		"--ssh-arg",
		action="append",
		default=[],
		dest="extra_ssh_args",
		help="Argumento adicional para ssh (se puede repetir)",
	)
	parser.add_argument(
		"--background",
		"-f",
		action="store_true",
		help="Ejecuta en segundo plano (ssh -f -N)",
	)
	parser.add_argument(
		"--command",
		"-c",
		help="Comando remoto opcional (si no se especifica usa -N)",
	)

	sub = parser.add_subparsers(dest="modo", required=True)

	local = sub.add_parser("local", help="Reenvío local (L)")
	local.add_argument("host", help="Host remoto (IP o DNS)")
	local.add_argument(
		"--forward",
		"-L",
		required=True,
		type=_validar_reenvio_local,
		help="El formato que deberías usar es: [bind_address:]local_port:dest_host:dest_port",
	)

	remoto = sub.add_parser("remoto", help="Reenvío remoto (R)")
	remoto.add_argument("host", help="Host remoto (IP o DNS)")
	remoto.add_argument(
		"--forward",
		"-R",
		required=True,
		type=_validar_reenvio_remoto,
		help="El formato que deberías usar es: [bind_address:]remote_port:dest_host:dest_port",
	)

	dinamico = sub.add_parser("socks", help="SOCKS dinámico (D)")
	dinamico.add_argument("host", help="Host remoto (IP o DNS)")
	dinamico.add_argument(
		"--forward",
		"-D",
		required=True,
		type=_validar_socks,
		help="El formato que deberías usar es: [bind_address:]socks_port",
	)

	sub.add_parser("interactivo", help="Modo interactivo con persistencia")
	sub.add_parser("ayuda", help="Guía rápida de uso en terminal")

	return parser


def _mostrar_ayuda_terminal() -> None:
	# Muestra una guía rápida para el modo no interactivo
	print("Guía rápida (modo no interactivo):")
	print("1) Elige el tipo de túnel: local, remoto o socks")
	print("2) Indica el host remoto (IP o DNS)")
	print("3) Define el reenvío con -L, -R o -D según el modo")
	print("4) Opcional: usuario, puerto, clave, keepalive, etc.")
	print("")
	print("Ejemplos:")
	print("  Local : python3 main.py local 192.168.1.10 -L 8080:127.0.0.1:80")
	print("  Remoto: python3 main.py remoto 192.168.1.10 -R 9090:127.0.0.1:22")
	print("  SOCKS : python3 main.py socks 192.168.1.10 -D 1080")


def _ejecutar_tunel(
	cfg: ConfigTunel,
	modo: str,
	reenvio: str,
	en_segundo_plano: bool,
	comando: Optional[str],
) -> int:
	# Construye y ejecuta el comando ssh completo
	args_ssh = _construir_args_ssh_base(cfg)

	if modo == "local":
		args_ssh += ["-L", reenvio]
	elif modo == "remoto":
		args_ssh += ["-R", reenvio]
	elif modo == "socks":
		args_ssh += ["-D", reenvio]
	else:
		print("Modo inválido.", file=sys.stderr)
		return 2

	if comando:
		# Si hay comando, no se usa -N
		args_ssh.append(cfg.destino())
		args_ssh.append(comando)
	else:
		# Sin comando, se usa -N y opcionalmente -f
		args_ssh.append("-N")
		if en_segundo_plano:
			args_ssh.append("-f")
		args_ssh.append(cfg.destino())

	return _ejecutar_ssh(args_ssh)


def _ejecutar_interactivo(argumentos_cli: Dict[str, Any]) -> int:
	# Modo interactivo con configuración persistente
	config_guardada = _cargar_config()
	print("Modo interactivo. Escribe 'ayuda' o '?' en cualquier paso para ver instrucciones.")

	modo_defecto = str(config_guardada.get("modo", "local"))
	modo = _pedir_texto(
		"Modo (local/remoto/socks)",
		defecto=modo_defecto,
		obligatorio=True,
		ayuda_texto=(
			"Elige el tipo de túnel:\n"
			"- local: abre un puerto local y lo reenvía al destino remoto\n"
			"- remoto: abre un puerto en el remoto y lo reenvía a tu equipo\n"
			"- socks: crea un proxy SOCKS dinámico"
		),
	)
	while modo not in ("local", "remoto", "socks"):
		print("Modo inválido. Usa local, remoto o socks.")
		modo = _pedir_texto(
			"Modo (local/remoto/socks)",
			defecto=modo_defecto,
			obligatorio=True,
			ayuda_texto=(
				"Elige el tipo de túnel:\n"
				"- local: abre un puerto local y lo reenvía al destino remoto\n"
				"- remoto: abre un puerto en el remoto y lo reenvía a tu equipo\n"
				"- socks: crea un proxy SOCKS dinámico"
			),
		)

	defecto_host = str(config_guardada.get("host", ""))
	host = _pedir_texto(
		"Host remoto",
		defecto=defecto_host,
		obligatorio=True,
		ayuda_texto="IP o nombre DNS del equipo remoto al que te conectarás por SSH.",
	)

	usuario = _pedir_texto(
		"Usuario SSH",
		defecto=str(config_guardada.get("usuario", "")),
		ayuda_texto="Usuario del servidor SSH remoto (por ejemplo: ubuntu, debian, kali).",
	)
	if not usuario:
		usuario = None

	puerto = _pedir_entero(
		"Puerto SSH",
		_obtener_entero_config(config_guardada.get("puerto"), 22),
		ayuda_texto="Puerto del servicio SSH en el remoto (normalmente 22).",
	)

	archivo_identidad = _pedir_texto(
		"Ruta a clave privada",
		defecto=str(config_guardada.get("archivo_identidad", "")),
		ayuda_texto="Ruta a tu clave privada (ej: ~/.ssh/id_rsa). Deja vacío si usas agente.",
	)
	if not archivo_identidad:
		archivo_identidad = None

	sin_pty = _pedir_si_no(
		"Desactivar pseudo-TTY",
		bool(config_guardada.get("sin_pty", False)),
		ayuda_texto="Recomendado para túneles: desactiva TTY. Usa s para sí, n para no.",
	)
	keepalive = _pedir_entero(
		"Intervalo keepalive (segundos)",
		_obtener_entero_config(config_guardada.get("keepalive"), 30),
		ayuda_texto="Segundos entre pings para mantener viva la sesión (ej: 30).",
	)

	args_ssh_extra = _pedir_lista(
		"Argumentos extra ssh (separados por coma)",
		list(config_guardada.get("args_ssh_extra", [])),
		ayuda_texto="Opcional: opciones extra para ssh. Ej: -v,-o,StrictHostKeyChecking=no",
	)

	defecto_reenvio = str(config_guardada.get("reenvio", ""))
	reenvio = _pedir_reenvio(modo, defecto_reenvio)

	en_segundo_plano = _pedir_si_no(
		"Ejecutar en segundo plano",
		bool(config_guardada.get("en_segundo_plano", False)),
		ayuda_texto="Si respondes s, el túnel queda en segundo plano (ssh -f -N).",
	)
	comando = _pedir_texto(
		"Comando remoto (vacío para -N)",
		defecto=str(config_guardada.get("comando", "")),
		ayuda_texto="Opcional: comando a ejecutar en el remoto. Vacío para solo túnel (-N).",
	)
	if not comando:
		comando = None

	config_tunel = ConfigTunel(
		usuario=usuario,
		host=host,
		puerto=puerto,
		archivo_identidad=archivo_identidad,
		sin_pty=sin_pty,
		keepalive=keepalive,
		args_ssh_extra=args_ssh_extra,
	)

	# Guardamos la configuración para próximos usos
	_guardar_config(
		{
			"modo": modo,
			"host": host,
			"usuario": usuario or "",
			"puerto": puerto,
			"archivo_identidad": archivo_identidad or "",
			"sin_pty": sin_pty,
			"keepalive": keepalive,
			"args_ssh_extra": args_ssh_extra,
			"reenvio": reenvio,
			"en_segundo_plano": en_segundo_plano,
			"comando": comando or "",
		}
	)

	return _ejecutar_tunel(config_tunel, modo, reenvio, en_segundo_plano, comando)


def principal() -> int:
	_requerir_ssh()

	# Si no hay argumentos, nos vamos al modo interactivo directamente
	if len(sys.argv) == 1:
		return _ejecutar_interactivo({})

	parser = _construir_parser()
	args = parser.parse_args()

	if args.modo == "interactivo":
		return _ejecutar_interactivo(vars(args))
	if args.modo == "ayuda":
		_mostrar_ayuda_terminal()
		return 0

	config_tunel = ConfigTunel(
		usuario=args.user,
		host=args.host,
		puerto=args.port,
		archivo_identidad=args.identity,
		sin_pty=args.no_pty,
		keepalive=args.keepalive,
		args_ssh_extra=args.extra_ssh_args,
	)

	return _ejecutar_tunel(
		config_tunel,
		args.modo,
		args.forward,
		args.background,
		args.command,
	)


if __name__ == "__main__":
	raise SystemExit(principal())
