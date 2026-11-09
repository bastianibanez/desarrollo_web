# Fit Express · demo estática

El frontend muestra datos ficticios locales y abre con la cuenta de Camila Soto iniciada. El panel muestra una identidad administrativa de ejemplo. No hay autenticación real, peticiones a la API, correos ni pagos. Las acciones de escritura están deshabilitadas. El carrito se guarda únicamente en el navegador, en una clave independiente de la aplicación anterior.

```sh
npm ci --prefix frontend
npm run dev --prefix frontend
```

Abrir http://localhost:5173. El navbar permite navegar entre Acceso, Panel y Mi cuenta. La pantalla Acceso muestra los formularios de ejemplo; `confirmar.html` lleva a la cuenta ficticia. El catálogo, cuenta, carrito y panel funcionan sin servicios backend. Las imágenes y Bootstrap continúan utilizando sus CDN existentes; la demo no es completamente offline.

```sh
npm run build --prefix frontend
```

Publicar el contenido de `frontend/dist/` en cualquier servidor estático. El Nginx de la imagen frontend no tiene proxies al backend. Desde un Compose ya configurado también se puede iniciar solo el frontend con `docker compose up -d --build --no-deps frontend`.

La prueba `services/tests/test_frontend.py` verifica datos, sesión ficticia y ausencia de dependencias de red/tokens. La antigua integración real del cliente se sustituyó por este contrato de demo; las pruebas del backend permanecen independientes.
