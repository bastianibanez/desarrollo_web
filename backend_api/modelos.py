from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


# === Modelos ===
class ProductoIn(BaseModel):
    nombre: str = Field(min_length=1)
    descripcion: str | None = None
    precio: int = Field(ge=0)
    stock: int = Field(ge=0)
    categoria_id: int


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
