const path = require('node:path');

module.exports = {
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,

  },
  build: {
    target: 'es2022',
    rolldownOptions: {
      input: {
        inicio: path.resolve(__dirname, 'index.html'),
        carrito: path.resolve(__dirname, 'carrito.html'),
        acceso: path.resolve(__dirname, 'acceso.html'),
        confirmar: path.resolve(__dirname, 'confirmar.html'),
        cuenta: path.resolve(__dirname, 'cuenta.html'),
        panel: path.resolve(__dirname, 'panel.html'),
      },
    },
  },
};
