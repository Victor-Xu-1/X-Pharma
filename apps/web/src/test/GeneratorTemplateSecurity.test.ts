import { createRequire } from "node:module";
import { expect, it } from "vitest";

const require = createRequire(import.meta.url);
const generatorRequire = createRequire(require.resolve("openapi-typescript-codegen"));
const handlebars = generatorRequire("handlebars");

it("rejects malformed AST block parameters before code generation", () => {
  const ast = handlebars.parse("{{#if ready}}safe{{/if}}");
  ast.body[0].program.blockParams = { length: "0/* invalid AST count */" };
  expect(() => handlebars.precompile(ast)).toThrow();
});

it("does not expose a Function constructor through a prototype's own property", () => {
  const render = handlebars.compile('{{lookup (lookup fn "__proto__") "constructor"}}');
  const result = render({ fn: function harmlessContext() {} }, { allowProtoMethodsByDefault: true });
  expect(result.trim()).toBe("");
});

it("keeps trusted string templates usable for the OpenAPI generator", () => {
  expect(
    handlebars.compile("{{name}}: {{#each values}}{{this}};{{/each}}")({ name: "schema", values: [0, false] }),
  ).toBe("schema: 0;false;");
});
