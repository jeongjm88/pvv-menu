const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const html = fs.readFileSync(__dirname + "/template.html", "utf8");
const code = html.slice(html.indexOf("const BANCHAN ="), html.indexOf("function featuredBadge"));
const context = vm.createContext({});
vm.runInContext(code, context);
const cases = [
  [["깍두기볶음밥&계란후라이", "멸치장국"], "깍두기볶음밥&계란후라이"],
  [["김치찌개", "쌀밥"], "김치찌개"],
  [["김치볶음밥", "미소장국"], "김치볶음밥"],
  [["깍두기/포기김치", "그린샐러드", "셀프비빔밥"], "그린샐러드"],
  [["포기김치", "그린샐러드"], "그린샐러드"],
  [["직화쭈꾸미삼겹살", "미역국"], "직화쭈꾸미삼겹살"],
];
let failures = 0;
for (const [items, expected] of cases) {
  context.items = items;
  const result = vm.runInContext("split(items)", context);
  try { assert.equal(result[0], expected); assert.equal(result[1].length, items.length-1); }
  catch (e) { failures++; console.error(expected + ": " + e.message); }
}
if (failures) process.exit(1);
console.log(`${cases.length} menu selection checks passed`);
