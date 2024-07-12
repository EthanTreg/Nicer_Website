module.exports = {
  env: {
    browser: true,
    es2022: true,
    jquery: true,
    es6: true,
  },
  extends: 'standard',
  overrides: [
  ],
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
  },
  rules: {
    semi: ['error', 'always'],
    'max-len': [
      'warn',
      {
        code: 80,
        tabWidth: 2,
        ignoreComments: false,
        ignoreUrls: true,
        ignoreStrings: false,
        ignoreTemplateLiterals: false,
      },
    ],
    'space-before-function-paren': ['error', {
      anonymous: 'always',
      asyncArrow: 'always',
      named: 'never',
    }],
    'comma-dangle': ['error', 'always-multiline'],
  },
  globals: {
    quality: 'writable',
  },
};
