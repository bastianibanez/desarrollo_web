const { Kind, valueFromASTUntyped } = require('graphql');
const { error } = require('./context');

function limits(document, operation, variables) {
  const fragments = Object.fromEntries(document.definitions.filter(d => d.kind === Kind.FRAGMENT_DEFINITION).map(d => [d.name.value, d]));
  function walk(selection, depth = 1, size = 20) {
    let maximum = depth, cost = 0;
    for (const node of selection.selections) {
      if (node.kind === Kind.FRAGMENT_SPREAD || node.kind === Kind.INLINE_FRAGMENT) {
        const [d, c] = walk(node.kind === Kind.FRAGMENT_SPREAD ? fragments[node.name.value].selectionSet : node.selectionSet, depth, size);
        maximum = Math.max(maximum, d); cost += c; continue;
      }
      const name = node.name.value;
      const args = Object.fromEntries((node.arguments || []).map(a => [a.name.value, valueFromASTUntyped(a.value, variables)]));
      const count = args.limite ?? (name === 'catalogo' ? 12 : size);
      if (!Number.isInteger(count) || count < 1 || count > 50) throw error('Paginación fuera de límites', 'QUERY_LIMIT');
      const multiplier = name === 'items' ? count : name === 'lineas' ? 50 : name === 'productos' && depth >= 4 ? 20 : name === 'categorias' ? 50 : 1;
      const [d, c] = node.selectionSet ? walk(node.selectionSet, depth + 1, count) : [depth, 0];
      maximum = Math.max(maximum, d); cost += multiplier * (1 + c);
    }
    return [maximum, cost];
  }
  return walk(operation.selectionSet);
}
const limitPlugin = {
  async requestDidStart() {
    return {
      async didResolveOperation({ document, operation, request }) {
        if (operation.operation !== 'query') throw error('Solo consultas Query', 'BAD_REQUEST');
        const variables = { ...request.variables };
        for (const variable of operation.variableDefinitions || []) {
          if (!(variable.variable.name.value in variables) && variable.defaultValue) variables[variable.variable.name.value] = valueFromASTUntyped(variable.defaultValue);
        }
        const [depth, cost] = limits(document, operation, variables);
        if (depth > 6 || cost > 2000) throw error('Consulta supera profundidad 6 o costo 2000', 'QUERY_LIMIT');
      }
    };
  }
};
module.exports = { limitPlugin };
