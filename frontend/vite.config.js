const path = require('node:path');

module.exports = {
  build: {
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
