module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  testMatch: ['**/tests/**/*.test.ts'],
  moduleNameMapper: {
    '^../lib/constants$': '<rootDir>/tests/stubs/constants.ts',
    '^../lib/computer-use-loop$': '<rootDir>/tests/stubs/computer-use-loop.ts'
  }
};
