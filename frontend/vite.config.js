const path = require('node:path');

module.exports = {
  build: {
    rolldownOptions: {
      input: {
        inicio: path.resolve(__dirname, 'index.html'),
        carrito: path.resolve(__dirname, 'carrito.html'),
      },
    },
  },
};
