from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Login(DTO):
    username: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class Registro(DTO):
    nombres: str = Field(min_length=1, max_length=120)
    apellidos: str = Field(min_length=1, max_length=120)
    rut: str = Field(min_length=3, max_length=20)
    email: EmailStr
    telefono: str = Field(min_length=1, max_length=30)
    direccion: str = Field(min_length=1, max_length=250)
    comuna_id: int = Field(gt=0)
    provincia: str = Field(min_length=1, max_length=120)
    region: str = Field(min_length=1, max_length=120)
    fecha_nacimiento: date
    sexo: str = Field(min_length=1, max_length=40)


class ClientePatch(DTO):
    nombres: str | None = Field(default=None, min_length=1, max_length=120)
    apellidos: str | None = Field(default=None, min_length=1, max_length=120)
    rut: str | None = Field(default=None, min_length=3, max_length=20)
    email: EmailStr | None = None
    telefono: str | None = Field(default=None, min_length=1, max_length=30)
    direccion: str | None = Field(default=None, min_length=1, max_length=250)
    comuna_id: int | None = Field(default=None, gt=0)
    provincia: str | None = Field(default=None, min_length=1, max_length=120)
    region: str | None = Field(default=None, min_length=1, max_length=120)
    fecha_nacimiento: date | None = None
    sexo: str | None = Field(default=None, min_length=1, max_length=40)
    activo: bool | None = None


class Verificar(DTO):
    cliente_id: int = Field(gt=0)
    codigo: str = Field(pattern=r"^\d{6}$")
    password: str = Field(min_length=8, max_length=256)


StaffRole = Literal["administrador", "cajero", "despacho", "dueno"]


class Funcionario(DTO):
    identificador: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=8, max_length=256)
    rol: StaffRole


class FuncionarioPatch(DTO):
    identificador: str | None = Field(default=None, min_length=1, max_length=254)
    password: str | None = Field(default=None, min_length=8, max_length=256)
    rol: StaffRole | None = None
    activo: bool | None = None


class Producto(DTO):
    nombre: str = Field(min_length=1, max_length=160)
    descripcion: str | None = Field(default=None, max_length=1000)
    precio: int = Field(ge=0, le=2_147_483_647)
    precio_oferta: int | None = Field(default=None, ge=0, le=2_147_483_647)
    stock: int = Field(ge=0, le=1_000_000)
    categoria_id: int = Field(gt=0)

    @model_validator(mode="after")
    def oferta(self):
        if self.precio_oferta is not None and self.precio_oferta >= self.precio:
            raise ValueError("Oferta inválida")
        return self


class Item(DTO):
    producto_id: int | None = Field(default=None, gt=0)
    combo_id: int | None = Field(default=None, gt=0)
    cantidad: int = Field(gt=0, le=1_000_000)

    @model_validator(mode="after")
    def referencia(self):
        if (self.producto_id is None) == (self.combo_id is None):
            raise ValueError("Producto XOR combo")
        return self


class Direccion(DTO):
    calle: str = Field(min_length=1, max_length=160)
    numero: str = Field(min_length=1, max_length=30)
    departamento: str | None = Field(default=None, max_length=60)
    comuna_id: int = Field(gt=0)


class Checkout(DTO):
    direccion: Direccion
    items: list[Item] = Field(min_length=1, max_length=50)


class Motivo(DTO):
    motivo: str = Field(min_length=1, max_length=1000)
    version: int | None = Field(default=None, ge=1)


class Transicion(DTO):
    version: int | None = Field(default=None, ge=1)


class Asignacion(DTO):
    cajero_id: int = Field(gt=0)


class InicioPago(DTO):
    orden_id: int = Field(gt=0)


class Solicitud(DTO):
    pedido_id: int = Field(gt=0)
    motivo: str = Field(min_length=1, max_length=1000)


class Decision(DTO):
    decision: Literal["aprobar", "rechazar"]
    motivo: str = Field(min_length=1, max_length=1000)
