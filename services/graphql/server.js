const express = require('express');
const { ApolloServer, gql } = require('apollo-server-express');
const { readFile } = require('node:fs/promises');
const { join } = require('node:path');
const { loadKeys, equal, createContext } = require('./context');
const { resolvers } = require('./resolvers');
const { limitPlugin } = require('./limits');

async function startServer() {
  const keys = await loadKeys();
  const app = express();
  app.get('/health', (_, res) => res.json({ status: 'ok', service: 'graphql' }));
  app.use((req, res, next) => {
    if (!equal(req.headers['x-gateway-secret'], keys.incoming.gateway)) return res.status(403).json({ detail: 'Gateway no autorizado' });
    next();
  });
  const typeDefs = gql(await readFile(join(__dirname, 'schema.graphql'), 'utf8'));
  const server = new ApolloServer({ typeDefs, resolvers, plugins: [limitPlugin],
    context: ({ req }) => createContext(keys, req.headers),
    formatError(err) {
      const code = err.extensions?.code || 'FIELD_ERROR';
      return { message: code === 'INTERNAL_SERVER_ERROR' ? 'No fue posible resolver el campo' : err.message,
        ...(err.path ? { path: err.path } : {}), extensions: { code } };
    }
  });
  await server.start();
  server.applyMiddleware({ app, path: '/graphql', cors: false, bodyParserConfig: { limit: '64kb' } });
  app.use((err, req, res, next) => res.status(err.status || 500).json({ detail: 'Solicitud inválida' }));
  const listener = app.listen(Number(process.env.PORT || 9000), '0.0.0.0', () => console.log('GraphQL privado iniciado'));
  const stop = () => listener.close(() => process.exit(0));
  process.on('SIGTERM', stop); process.on('SIGINT', stop);
}
startServer().catch(() => { console.error('GraphQL no pudo iniciar; revisar identidad y configuración'); process.exit(1); });
