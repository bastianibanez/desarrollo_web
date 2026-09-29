"""Envío de correo. Versión mock: escribe el mensaje en la consola en vez de enviarlo.

Para usar un servicio real, reemplazar el cuerpo de enviar_correo por la llamada HTTP
del proveedor (URL, autenticación y payload dependen de él). Si el proveedor falla debe
lanzar una excepción; el resto del backend no cambia.
"""


def enviar_correo(destino: str, asunto: str, cuerpo: str) -> None:
    print(f"[correo mock] Para: {destino}\n  Asunto: {asunto}\n  {cuerpo}", flush=True)
