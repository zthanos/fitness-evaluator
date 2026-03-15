/**
 * page-loader.js
 *
 * Φορτώνει HTML views από τον server με in-memory cache.
 */

export class PageLoader {
    static _cache = new Map();
  
    static async load(path) {
      if (this._cache.has(path)) return this._cache.get(path);
  
      const response = await fetch(path);
      if (!response.ok) throw new Error(`PageLoader: "${path}" (${response.status})`);
  
      const html = await response.text();
      this._cache.set(path, html);
      return html;
    }
  
    static async preloadAll(paths) {
      await Promise.all(paths.map(p => this.load(p)));
    }
  }