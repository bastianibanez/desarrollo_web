from typing import Literal

from datetime import date
from pydantic import BaseModel, EmailStr, Field, model_validator


# === Modelos ===
class ProductoIn(BaseModel):
    nombre: str = Field(min_length=1)
    descripcion: str | None = None
    precio: int = Field(ge=0)
    precio_oferta: int | None = Field(default=None, ge=0)
    stock: int = Field(ge=0)
    categoria_id: int

    @model_validator(mode="after")
    def oferta_menor_que_precio(self):
        if self.precio_oferta is not None and self.precio_oferta >= self.precio:
            raise ValueError("precio_oferta debe ser menor que precio")
        return self


class ClienteIn(BaseModel):
    nombres: str = Field(min_length=1)
    apellidos: str = Field(min_length=1)
    rut: str = Field(min_length=1)
    email: EmailStr
    telefono: str | None = None


class DireccionIn(BaseModel):
    calle: str = Field(min_length=1)
    numero: str = Field(min_length=1)
    departamento: str | None = None
    comuna_id: int


class ItemIn(BaseModel):
    producto_id: int | None = None
    combo_id: int | None = None
    cantidad: int = Field(ge=1)

    @model_validator(mode="after")
    def producto_xor_combo(self):
        if (self.producto_id is None) == (self.combo_id is None):
            raise ValueError("Cada item requiere producto_id o combo_id (no ambos)")
        return self


class OrdenIn(BaseModel):
    cliente: ClienteIn
    direccion: DireccionIn
    items: list[ItemIn] = Field(min_length=1)


# === Tipos compartidos ===
EstadoOrden = Literal[
    "pendiente", "pagada", "preparando", "enviada", "entregada", "cancelada"
]


# === Modelos de salida ===
class CategoriaOut(BaseModel):
    id: int
    nombre: str
    created_at: str


class ProductoOut(BaseModel):
    id: int
    nombre: str
    descripcion: str | None
    precio: int
    precio_oferta: int | None
    stock: int
    categoria_id: int
    categoria: str
    created_at: str
    updated_at: str


class ProductoEnComboOut(BaseModel):
    id: int
    nombre: str
    cantidad: int


class ComboOut(BaseModel):
    id: int
    nombre: str
    descripcion: str | None
    precio: int
    precio_oferta: int | None
    created_at: str
    updated_at: str
    productos: list[ProductoEnComboOut]


class ComunaOut(BaseModel):
    id: int
    nombre: str
    ciudad: str
    region: str
    costo_envio: int


class OrdenCreadaOut(BaseModel):
    id: int
    subtotal: int
    costo_envio: int
    total: int


class LineaOrdenOut(BaseModel):
    producto_id: int | None
    combo_id: int | None
    cantidad: int
    precio_unitario: int


class OrdenOut(BaseModel):
    id: int
    cliente_id: int
    nombres: str
    apellidos: str
    rut: str
    email: str
    telefono: str | None
    calle: str
    numero: str
    departamento: str | None
    comuna_id: int
    comuna: str
    subtotal: int
    costo_envio: int
    descuento: int
    total: int
    estado: EstadoOrden
    created_at: str
    updated_at: str
    lineas: list[LineaOrdenOut]


class ClienteRegistroIn(BaseModel):
    nombres: str = Field(min_length=1)
    apellidos: str = Field(min_length=1)
    rut: str = Field(min_length=3)
    direccion: str = Field(min_length=1)
    comuna_id: int
    provincia: str = Field(min_length=1)
    region: str = Field(min_length=1)
    fecha_nacimiento: date
    sexo: str = Field(min_length=1)
    email: EmailStr
    telefono: str = Field(min_length=1)


class VerificarCorreoIn(BaseModel):
    cliente_id: int
    codigo: str = Field(pattern=r"^\d{6}$")
    password: str = Field(min_length=8)


class LoginIn(BaseModel):
    identificador: str
    password: str
