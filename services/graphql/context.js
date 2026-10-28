const { GraphQLError } = require('graphql');
const { timingSafeEqual } = require('node:crypto');
const { readFile } = require('node:fs/promises');

function error(message, code = 'DEPENDENCY_UNAVAILABLE') {
  const result = new GraphQLError(message);
  result.extensions = { code };
  return result;
}
function equal(a, b) {
  const left = Buffer.from(a || ''), right = Buffer.from(b || '');
  return left.length === right.length && timingSafeEqual(left, right);
}
async function loadKeys() {
  // Solo las pruebas inyectan identidades; el arranque normal siempre consulta Vault.
  if (process.env.NODE_ENV === 'test' && process.env.TEST_IDENTITY_FILE) {
    return JSON.parse(await readFile(process.env.TEST_IDENTITY_FILE, 'utf8'));
  }
  const token = (await readFile(process.env.VAULT_TOKEN_FILE || '/run/identity/token', 'utf8')).trim();
  const response = await fetch(`${process.env.VAULT_ADDR || 'http://vault:8200'}/v1/secret/data/services/graphql`, {
    headers: { 'X-Vault-Token': token }, signal: AbortSignal.timeout(3000)
  });
  if (!response.ok) throw new Error('Identidad de GraphQL no disponible');
  return (await response.json()).data.data;
}
function readUser(headers) {
  if (!headers['x-authenticated-user-id']) return null;
  const role = headers['x-authenticated-roles'];
  if (!['cliente', 'administrador', 'cajero', 'despacho', 'dueno'].includes(role)) {
    throw error('Contexto de identidad inválido', 'UNAUTHENTICATED');
  }
  return { id: Number(headers['x-authenticated-user-id']), rol: role };
}
function createContext(keys, headers) {
  const user = readUser(headers);
  const deadline = AbortSignal.timeout(10000);
  return {
    user,
    require(roles) {
      if (!user) throw error('Sesión requerida', 'UNAUTHENTICATED');
      if (roles && !roles.includes(user.rol)) throw error('Campo u operación no autorizados', 'FORBIDDEN');
    },
    async call(service, method, path, body, params) {
      const url = new URL((process.env[`${service.toUpperCase()}_URL`] || `http://${service}:9000`) + path);
      for (const [key, value] of Object.entries(params || {})) {
        if (value !== null && value !== undefined) url.searchParams.set(key, String(value));
      }
      const outgoing = { 'Content-Type': 'application/json', 'X-Gateway-Secret': keys.outgoing[service] };
      for (const [key, value] of Object.entries(headers)) {
        if (key.startsWith('x-authenticated-') || key === 'x-request-id') outgoing[key] = value;
      }
      let response;
      try {
        response = await fetch(url, { method, headers: outgoing, body: body ? JSON.stringify(body) : undefined,
          signal: AbortSignal.any([deadline, AbortSignal.timeout(3000)]) });
      } catch {
        throw error(deadline.aborted ? 'Plazo de consulta agotado' : 'Servicio dependiente no disponible', deadline.aborted ? 'TIMEOUT' : 'DEPENDENCY_UNAVAILABLE');
      }
      if (!response.ok) throw error('Recurso no disponible o acceso no autorizado', {
        401: 'UNAUTHENTICATED', 403: 'FORBIDDEN', 404: 'NOT_FOUND', 422: 'BAD_USER_INPUT'
      }[response.status] || 'DEPENDENCY_UNAVAILABLE');
      return response.json();
    }
  };
}
module.exports = { error, equal, loadKeys, createContext };
