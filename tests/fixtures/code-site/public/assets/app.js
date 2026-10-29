// The invented site's script: it loads a chunk the HTML never names, as a bundler's code splitting does.
import("./chunk.js").then((m) => { document.documentElement.dataset.chunk = m.version; });
