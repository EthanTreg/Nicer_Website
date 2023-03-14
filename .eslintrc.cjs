module.exports = {
  env: {
    browser: true,
    es2022: true,
    jquery: true,
    es6: true
  },
  extends: 'standard',
  overrides: [
  ],
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'script'
  },
  rules: {
    semi: [2, 'always']
  },
  globals: {
    quality: 'writable'
  }
};
