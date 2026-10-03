// Scoped npm override: only Next ESLint's fast-glob imports this adapter.
// Keep fast-glob's traversal and use Picomatch for the same makeRe/scan APIs;
// replace the vulnerable braces AST walkers with maintained brace-expansion.
import picomatch from "picomatch";
import { expand } from "brace-expansion";
const MAX_LENGTH = 10_000;
const MAX_DEPTH = 128;
const MAX_EXPANSIONS = 1_000;

function validate(pattern) {
  if (typeof pattern !== "string") throw new TypeError("glob pattern must be a string");
  if (pattern.length > MAX_LENGTH) throw new SyntaxError("glob pattern exceeds length limit");
  let depth = 0;
  for (let i = 0; i < pattern.length; i++) {
    if (pattern[i] === "\\") { i++; continue; }
    if (pattern[i] === "{" && ++depth > MAX_DEPTH) throw new SyntaxError("glob brace nesting exceeds limit");
    if (pattern[i] === "}" && depth > 0) depth--;
  }
}

export const makeRe = (pattern, options) => { validate(pattern); return picomatch.makeRe(pattern, options); };
export const scan = (pattern, options) => { validate(pattern); return picomatch.scan(pattern, options); };
export const braces = (pattern, options = {}) => {
  validate(pattern);
  if (options.expand !== true) throw new TypeError("Next glob adapter requires expansion mode");
  // One sentinel result makes overflow observable; never silently drop roots.
  // Input length and count bound output size (<= 10,010,000 characters).
  const results = expand(pattern, { max: MAX_EXPANSIONS + 1, maxLength: Infinity, maxDepth: MAX_DEPTH });
  if (results.length > MAX_EXPANSIONS) throw new SyntaxError("glob brace expansion exceeds limit");
  return options.nodupes ? [...new Set(results)] : results;
};
