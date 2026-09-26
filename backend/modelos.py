from pydantic import BaseModel, Field, EmailStr, model_validator


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
